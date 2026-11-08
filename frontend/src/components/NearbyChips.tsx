import React, { useEffect, useState } from "react";
import { ScrollView } from "react-native";

import { api, Loc } from "@/src/api";
import { Chip, space } from "@/src/components/ui";

const ICON: Record<string, any> = { railway_station: "train-outline", bus_terminal: "bus-outline", bus_stop: "bus-outline", airport: "airplane-outline" };

/** Suggests real nearby bus stops / stations / airports (OpenStreetMap) as pickup or drop points. */
export function NearbyChips({ loc, onPick, testID }: { loc: Loc | null; onPick: (name: string) => void; testID: string }) {
  const [rows, setRows] = useState<(Loc & { distance_m: number })[]>([]);
  useEffect(() => {
    setRows([]);
    if (!loc) return;
    api(`/geo/nearby?lat=${loc.lat}&lng=${loc.lng}`).then((r) => setRows(r.results.slice(0, 8))).catch(() => {});
  }, [loc?.lat, loc?.lng]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!rows.length) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }} keyboardShouldPersistTaps="handled">
      {rows.map((r, i) => (
        <Chip key={r.loc_id} testID={`${testID}-${i}`} icon={ICON[r.type] ?? "location-outline"} label={`${r.name} · ${r.distance_m < 1000 ? `${r.distance_m} m` : `${(r.distance_m / 1000).toFixed(1)} km`}`} onPress={() => onPick(r.name)} />
      ))}
    </ScrollView>
  );
}
