import * as Location from "expo-location";
import React, { useEffect, useState } from "react";
import { View } from "react-native";

import { api } from "@/src/api";
import { OsmMap } from "@/src/components/OsmMap";
import { Badge, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const STEPS = [["confirmed", "Booking confirmed"], ["arriving", "I am arriving"], ["arrived", "Arrived at pickup"], ["started", "Trip started"], ["completed", "Trip completed"]] as const;

export const tripStage = (h: any) => h.status === "completed" ? 4 : h.status === "started" ? 3 : h.arrived_at ? 2 : h.arriving_at ? 1 : 0;

export function TripTimeline({ h }: { h: any }) {
  const { colors } = useTheme();
  const at = tripStage(h);
  return (
    <View testID="hire-timeline" style={{ gap: space.sm }}>
      {STEPS.map(([k, label], i) => (
        <View key={k} testID={`hire-step-${k}`} style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
          <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: i <= at ? colors.success : colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
            <T size={11} weight="800" color={i <= at ? "#fff" : colors.muted}>{i + 1}</T>
          </View>
          <T size={13} weight={i === at ? "800" : "500"} color={i <= at ? colors.onSurface : colors.muted}>{label}</T>
        </View>
      ))}
    </View>
  );
}

/** Driver: shares GPS every 15 s after "I am arriving" until the trip ends. Customer: sees the live position. Nobody else can read it. */
export function LiveLocation({ h }: { h: any }) {
  const { colors } = useTheme();
  const [pos, setPos] = useState<{ lat: number; lng: number; updated_at?: string } | null>(null);
  const [msg, setMsg] = useState("");
  const live = !!h.arriving_at && ["confirmed", "started"].includes(h.status);
  useEffect(() => {
    if (!live) return;
    let stop = false;
    const tick = async () => {
      try {
        if (h.is_driver) {
          const { status } = await Location.requestForegroundPermissionsAsync();
          if (status !== "granted") return setMsg("Allow location access so the customer can see you arriving");
          const c = (await Location.getCurrentPositionAsync({})).coords;
          if (stop) return;
          await api(`/hire/bookings/${h.booking_id}/location`, { body: { lat: c.latitude, lng: c.longitude } });
          setPos({ lat: c.latitude, lng: c.longitude });
          setMsg("");
        } else {
          const r = await api(`/hire/bookings/${h.booking_id}/location`);
          if (!stop) setPos(r);
        }
      } catch (e: any) { setMsg(e.message); }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => { stop = true; clearInterval(id); };
  }, [live, h.booking_id, h.is_driver]);
  if (!live) return null;
  return (
    <View testID="hire-live-location" style={{ gap: space.sm }}>
      <Badge icon="navigate" label={h.is_driver ? "Sharing your live location with this customer" : "Driver live location"} tone="success" />
      {pos ? <OsmMap testID="hire-live-map" markers={[{ lat: pos.lat, lng: pos.lng, color: colors.brandTertiary, label: "Driver" }]} centerKey={`${pos.lat},${pos.lng}`} zoom={14}
        style={{ height: 200, borderRadius: radius.lg, overflow: "hidden" }} /> : <T size={12} color={colors.muted}>{h.is_driver ? "Getting your location…" : "Waiting for the driver's location…"}</T>}
      {msg ? <T testID="hire-live-msg" size={12} color={colors.error}>{msg}</T> : null}
    </View>
  );
}
