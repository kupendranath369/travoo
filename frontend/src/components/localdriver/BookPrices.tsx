import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";

import { api, Loc } from "@/src/api";
import { T, radius, space } from "@/src/components/ui";
import { inr } from "@/src/i18n";
import { useTheme } from "@/src/theme";

type Est = { distance_km: number; billable_km: number; days: number; driver_allowance: number; estimates: { vehicle_type: string; rate_per_km: number; low: number; high: number }[] };

/** Estimated Book a Car price for each car type; tapping a row picks that type. */
export function BookPrices({ pickup, dest, stype, days, vtype, onPick }: { pickup: Loc | null; dest: Loc | null; stype: string; days: number; vtype: string; onPick: (v: string) => void }) {
  const { colors } = useTheme();
  const [est, setEst] = useState<Est | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!pickup || !dest) return setEst(null);
    let live = true;
    setBusy(true); setErr("");
    api(`/route/estimate?points=${pickup.lat},${pickup.lng};${dest.lat},${dest.lng}`)
      .then((r) => api(`/hire/book-estimate?km=${Math.max(1, r.distance_km)}&service_type=${stype}&days=${days}`))
      .then((e) => { if (live) setEst(e); })
      .catch((e) => { if (live) { setEst(null); setErr(e.message); } })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [pickup?.loc_id, dest?.loc_id, pickup, dest, stype, days]);

  if (!pickup || !dest) return <T testID="book-price-hint" size={12} color={colors.muted}>Enter pickup and destination to see estimated prices.</T>;
  if (busy) return <ActivityIndicator testID="book-price-loading" color={colors.brand} />;
  if (err || !est) return <T testID="book-price-error" size={12} color={colors.error}>{err || "Could not estimate prices right now."}</T>;
  return (
    <View testID="book-price-card" style={{ gap: space.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Ionicons name="pricetags-outline" size={16} color={colors.brand} />
        <T weight="800">Estimated price</T>
      </View>
      <T testID="book-price-distance" size={12} color={colors.muted}>{est.distance_km} km trip · {est.billable_km} km charged · {est.days} day{est.days > 1 ? "s" : ""}</T>
      {est.estimates.map((e) => {
        const on = vtype === e.vehicle_type;
        return (
          <Pressable key={e.vehicle_type} testID={`book-price-${e.vehicle_type}`} onPress={() => onPick(e.vehicle_type)}
            style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: space.sm, borderRadius: radius.md, borderWidth: 1.5,
              borderColor: on ? colors.brand : colors.border, backgroundColor: on ? colors.brandSoft : colors.surface }}>
            <View>
              <T weight="700">{e.vehicle_type.toUpperCase()}</T>
              <T size={11} color={colors.muted}>{inr(e.rate_per_km)}/km</T>
            </View>
            <T testID={`book-price-${e.vehicle_type}-amount`} weight="800" color={on ? colors.brand : undefined}>{inr(e.low)} – {inr(e.high)}</T>
          </Pressable>
        );
      })}
      <T size={11} color={colors.muted}>Includes driver allowance {inr(est.driver_allowance)}. Tolls, parking and state permits are extra. The final price is agreed with the driver; pay them directly.</T>
    </View>
  );
}
