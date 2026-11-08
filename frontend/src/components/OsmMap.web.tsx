import React, { useEffect, useMemo, useRef } from "react";
import { View } from "react-native";

import type { OsmMapProps } from "@/src/components/OsmMap";
import { mapHtml } from "@/src/mapHtml";

/** Web build of OsmMap: same Leaflet page rendered in an iframe, messages via postMessage. */
export function OsmMap({ markers, lines, pick, centerKey, zoom, onPick, onLinePress, style, testID }: OsmMapProps) {
  const id = useRef(`m${Math.random().toString(36).slice(2)}`).current;
  const cb = useRef({ onPick, onLinePress });
  cb.current = { onPick, onLinePress };
  const shape = JSON.stringify({ markers, lines, zoom });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const html = useMemo(() => mapHtml({ id, markers, lines, pick, zoom }), [shape, centerKey]);

  useEffect(() => {
    const h = (e: MessageEvent) => {
      if (!e.data || e.data.travooMap !== id) return;
      const m = JSON.parse(e.data.data);
      if (m.type === "pick") cb.current.onPick?.(m.lat, m.lng);
      if (m.type === "line") cb.current.onLinePress?.(m.id);
    };
    window.addEventListener("message", h);
    return () => window.removeEventListener("message", h);
  }, [id]);

  return (
    <View testID={testID} style={[{ height: 220, borderRadius: 12, overflow: "hidden" }, style]}>
      {React.createElement("iframe", { srcDoc: html, title: "map", style: { border: 0, width: "100%", height: "100%" } })}
    </View>
  );
}
