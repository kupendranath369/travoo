/** Builds a self-contained Leaflet + OpenStreetMap page used by OsmMap on native (WebView) and web (iframe). */
export type MapMarker = { lat: number; lng: number; color: string; label?: string };
export type MapLine = { coords: [number, number][]; color: string; width?: number; dashed?: boolean; id?: number };
export type MapConfig = {
  id: string;
  markers?: MapMarker[];
  lines?: MapLine[];
  pick?: { lat: number; lng: number; color: string } | null;
  zoom?: number;
};

export function mapHtml(cfg: MapConfig) {
  return `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#m{margin:0;height:100%;width:100%;background:#e8eef5}
.pin{width:26px;height:26px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)}
.leaflet-control-attribution{font-size:9px}</style></head><body><div id="m"></div><script>
var C=${JSON.stringify(cfg)};
function post(m){var s=JSON.stringify(m);if(window.ReactNativeWebView){window.ReactNativeWebView.postMessage(s)}else{parent.postMessage({travooMap:C.id,data:s},'*')}}
var map=L.map('m',{zoomControl:true,attributionControl:true}).setView([22.5,79],5);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
var pts=[];
(C.lines||[]).forEach(function(l){var pl=L.polyline(l.coords,{color:l.color,weight:l.width||5,opacity:.9,dashArray:l.dashed?'6 8':null}).addTo(map);
 if(l.id!==undefined){pl.on('click',function(){post({type:'line',id:l.id})})}l.coords.forEach(function(c){pts.push(c)})});
(C.markers||[]).forEach(function(k){var mk=L.circleMarker([k.lat,k.lng],{radius:8,color:'#fff',weight:3,fillColor:k.color,fillOpacity:1}).addTo(map);if(k.label)mk.bindTooltip(k.label);pts.push([k.lat,k.lng])});
if(C.pick){var icon=L.divIcon({className:'',html:'<div class="pin" style="background:'+C.pick.color+'"></div>',iconSize:[26,26],iconAnchor:[13,30]});
 var pm=L.marker([C.pick.lat,C.pick.lng],{draggable:true,icon:icon}).addTo(map);
 function send(ll){post({type:'pick',lat:ll.lat,lng:ll.lng})}
 pm.on('dragend',function(){send(pm.getLatLng())});
 map.on('click',function(e){pm.setLatLng(e.latlng);send(e.latlng)});
 map.setView([C.pick.lat,C.pick.lng],C.zoom||15);}
else if(pts.length>1){map.fitBounds(pts,{padding:[28,28]})}else if(pts.length===1){map.setView(pts[0],C.zoom||13)}
post({type:'ready'});
</script></body></html>`;
}
