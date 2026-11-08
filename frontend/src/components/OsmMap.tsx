import React, { useMemo, useRef } from "react";
import { StyleProp, View, ViewStyle } from "react-native";
import { WebView } from "react-native-webview";

import { MapLine, MapMarker, mapHtml } from "@/src/mapHtml";

export type OsmMapProps = {
  markers?: MapMarker[];
  lines?: MapLine[];
  pick?: { lat: number; lng: number; color: string } | null;
  /** Change this to re-centre the pin (e.g. after "use current location"); tapping the map never reloads it. */
  centerKey?: string;
  zoom?: number;
  onPick?: (lat: number, lng: number) => void;
  onLinePress?: (id: number) => void;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/** OpenStreetMap (Leaflet) map: route lines, markers and a draggable pin. Native build uses a WebView. */
export function OsmMap({ markers, lines, pick, centerKey, zoom, onPick, onLinePress, style, testID }: OsmMapProps) {
  const id = useRef(`m${Math.random().toString(36).slice(2)}`).current;
  const shape = JSON.stringify({ markers, lines, zoom });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const html = useMemo(() => mapHtml({ id, markers, lines, pick, zoom }), [shape, centerKey]);
  return (
    <View testID={testID} style={[{ height: 220, borderRadius: 12, overflow: "hidden" }, style]}>
      <WebView
        originWhitelist={["*"]}
        source={{ html, baseUrl: "https://travoo.app/" }}
        nestedScrollEnabled
        setBuiltInZoomControls={false}
        onMessage={(e) => {
          try {
            const m = JSON.parse(e.nativeEvent.data);
            if (m.type === "pick") onPick?.(m.lat, m.lng);
            if (m.type === "line") onLinePress?.(m.id);
          } catch {}
        }}
      />
    </View>
  );
}
