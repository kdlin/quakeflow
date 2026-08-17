from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _rows(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [
        {column: _json_value(value) for column, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


def build_dashboard(connection: duckdb.DuckDBPyConnection, target: Path) -> Path:
    events = _rows(
        connection,
        """
        SELECT event_id, magnitude, magnitude_band, place, occurred_at,
               longitude, latitude, depth_km, alert, tsunami, detail_url
        FROM earthquakes ORDER BY occurred_at DESC LIMIT 1500
        """,
    )
    daily = _rows(connection, "SELECT * FROM gold_daily_metrics ORDER BY event_date")
    regions = _rows(connection, "SELECT * FROM gold_region_metrics LIMIT 12")
    distribution = _rows(connection, "SELECT * FROM gold_magnitude_distribution")
    quality = _rows(
        connection,
        """
        SELECT check_name, passed, observed_value, expectation
        FROM quality_results
        WHERE run_id = (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1)
        ORDER BY check_name
        """,
    )
    totals = connection.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(magnitude), 0),
               COALESCE(ROUND(AVG(magnitude), 2), 0),
               COALESCE(SUM(CASE WHEN tsunami THEN 1 ELSE 0 END), 0),
               MAX(occurred_at)
        FROM earthquakes
        """
    ).fetchone()

    data = {
        "events": events,
        "daily": daily,
        "regions": regions,
        "distribution": distribution,
        "quality": quality,
        "metrics": {
            "event_count": totals[0],
            "max_magnitude": totals[1],
            "average_magnitude": totals[2],
            "tsunami_events": totals[3],
            "latest_event": _json_value(totals[4]),
        },
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    encoded = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = _template().replace("__QUAKEFLOW_DATA__", encoded)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def _template() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Live earthquake analytics produced by the QuakeFlow data pipeline.">
  <title>QuakeFlow | Earthquake Intelligence</title>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
  <style>
    :root{--bg:#08090b;--panel:#111318;--line:#232731;--text:#edf0f6;--muted:#89909f;--cyan:#64d8ff;--pink:#d57bba;--green:#8fe3a0;--orange:#ffad66;--red:#ff6b6b}
    *{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 70% -20%,#162330 0,transparent 34%),var(--bg);color:var(--text);font:14px Inter,ui-sans-serif,system-ui,sans-serif}
    main{max-width:1440px;margin:auto;padding:28px}.top{display:flex;align-items:end;justify-content:space-between;margin-bottom:24px}.eyebrow{color:var(--cyan);font:600 11px ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase}h1{font-size:38px;letter-spacing:-.04em;margin:6px 0 0}.live{color:var(--green);font:600 12px ui-monospace,monospace}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 12px var(--green);margin-right:8px}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}.card,.panel{border:1px solid var(--line);background:linear-gradient(145deg,rgba(19,22,28,.96),rgba(12,14,18,.96));border-radius:12px}.card{padding:17px}.label{color:var(--muted);font:600 10px ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}.value{font-size:28px;font-weight:650;margin-top:6px;letter-spacing:-.03em}.grid{display:grid;grid-template-columns:1.65fr 1fr;gap:12px}.panel{padding:15px}.panel h2{font-size:12px;font-weight:650;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px;color:#b8beca}.chart{height:410px}.small{height:300px}.stack{display:grid;gap:12px}.quality{display:flex;flex-wrap:wrap;gap:8px;padding:8px 2px 0}.chip{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--muted);font:11px ui-monospace,monospace}.chip.ok{border-color:#8fe3a044;color:var(--green)}footer{display:flex;justify-content:space-between;color:var(--muted);font:11px ui-monospace,monospace;margin-top:18px}a{color:var(--cyan)}
    @media(max-width:850px){main{padding:16px}.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.top{align-items:start;flex-direction:column;gap:10px}.chart{height:340px}}
  </style>
</head>
<body><main>
  <div class="top"><div><div class="eyebrow">USGS real-time data lakehouse</div><h1>QuakeFlow</h1></div><div class="live"><span class="dot"></span>PIPELINE HEALTHY</div></div>
  <section class="metrics">
    <div class="card"><div class="label">Events loaded</div><div class="value" id="event-count"></div></div>
    <div class="card"><div class="label">Maximum magnitude</div><div class="value" id="max-mag"></div></div>
    <div class="card"><div class="label">Average magnitude</div><div class="value" id="avg-mag"></div></div>
    <div class="card"><div class="label">Tsunami flags</div><div class="value" id="tsunami-count"></div></div>
  </section>
  <section class="grid">
    <div class="panel"><h2>Global event map</h2><div id="map" class="chart"></div></div>
    <div class="stack">
      <div class="panel"><h2>Magnitude distribution</h2><div id="magnitude" class="small"></div></div>
      <div class="panel"><h2>Data quality</h2><div id="quality" class="quality"></div></div>
    </div>
    <div class="panel"><h2>Events by day</h2><div id="timeline" class="small"></div></div>
    <div class="panel"><h2>Most active regions</h2><div id="regions" class="small"></div></div>
  </section>
  <footer><span id="generated"></span><a href="https://github.com/kdlin/quakeflow">View pipeline source</a></footer>
</main>
<script>
const D=__QUAKEFLOW_DATA__, C={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#89909f',family:'ui-monospace,monospace'},margin:{l:45,r:15,t:10,b:40}};
document.querySelector('#event-count').textContent=D.metrics.event_count.toLocaleString();document.querySelector('#max-mag').textContent=D.metrics.max_magnitude.toFixed(1);document.querySelector('#avg-mag').textContent=D.metrics.average_magnitude.toFixed(2);document.querySelector('#tsunami-count').textContent=D.metrics.tsunami_events;document.querySelector('#generated').textContent='Generated '+new Date(D.generated_at).toLocaleString();
Plotly.newPlot('map',[{type:'scattergeo',mode:'markers',lat:D.events.map(x=>x.latitude),lon:D.events.map(x=>x.longitude),text:D.events.map(x=>`M ${x.magnitude??'?'} · ${x.place}<br>${new Date(x.occurred_at).toLocaleString()}<br>Depth ${x.depth_km} km`),hoverinfo:'text',marker:{size:D.events.map(x=>Math.max(4,(x.magnitude??0)*2.2)),color:D.events.map(x=>x.magnitude??0),colorscale:[[0,'#64d8ff'],[.55,'#d57bba'],[1,'#ff6b6b']],cmin:0,cmax:7,opacity:.82,line:{width:.4,color:'#08090b'},colorbar:{title:'Magnitude',thickness:8}}}],{...C,geo:{projection:{type:'natural earth'},bgcolor:'transparent',showland:true,landcolor:'#171a20',showocean:true,oceancolor:'#0b1016',showcountries:true,countrycolor:'#2a303a',showcoastlines:true,coastlinecolor:'#343b46'},margin:{l:0,r:0,t:0,b:0}},{responsive:true,displaylogo:false});
Plotly.newPlot('magnitude',[{type:'pie',labels:D.distribution.map(x=>x.magnitude_band),values:D.distribution.map(x=>x.event_count),hole:.68,marker:{colors:['#64d8ff','#80bfff','#d57bba','#ffad66','#ff836d','#ff6b6b','#e44f65','#89909f']},textinfo:'label+percent',textfont:{size:10}}],{...C,showlegend:false,margin:{l:10,r:10,t:10,b:10}},{responsive:true,displaylogo:false});
Plotly.newPlot('timeline',[{type:'bar',x:D.daily.map(x=>x.event_date),y:D.daily.map(x=>x.event_count),marker:{color:'#64d8ff'}}],{...C,xaxis:{gridcolor:'#20242c'},yaxis:{gridcolor:'#20242c',title:'Events'}},{responsive:true,displaylogo:false});
Plotly.newPlot('regions',[{type:'bar',orientation:'h',y:D.regions.map(x=>x.region).reverse(),x:D.regions.map(x=>x.event_count).reverse(),marker:{color:'#d57bba'}}],{...C,xaxis:{gridcolor:'#20242c'},yaxis:{gridcolor:'transparent'},margin:{l:110,r:15,t:10,b:40}},{responsive:true,displaylogo:false});
document.querySelector('#quality').innerHTML=D.quality.map(q=>`<span class="chip ${q.passed?'ok':''}" title="${q.expectation}">${q.passed?'✓':'✕'} ${q.check_name}</span>`).join('');if(D.quality.some(q=>!q.passed)){document.querySelector('.live').innerHTML='<span class="dot" style="background:#ffad66"></span>QUALITY WARNING'}
</script></body></html>"""
