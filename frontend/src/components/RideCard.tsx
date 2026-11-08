import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React from "react";
import { View } from "react-native";

import { publicPhoto } from "@/src/api";
import { Avatar, Badge, Card, Rating, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export const fmtDur = (m: number) => `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;

export function RideCard({ trip, seats = 1 }: { trip: any; seats?: number }) {
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const v = trip.vehicle || {};
  return (
    <Card testID={`ride-card-${trip.trip_id}`} onPress={() => router.push(`/trip/${trip.trip_id}?seats=${seats}`)} style={{ gap: space.md }}>
      <View style={{ flexDirection: "row", gap: space.md }}>
        <View style={{ alignItems: "center", paddingTop: 4 }}>
          <View style={{ width: 10, height: 10, borderRadius: 5, borderWidth: 2, borderColor: colors.brandPrimary }} />
          <View style={{ width: 2, flex: 1, backgroundColor: colors.border, marginVertical: 2 }} />
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.brandTertiary }} />
        </View>
        <View style={{ flex: 1, gap: space.md }}>
          <View>
            <T size={16} weight="800">{trip.time} · {trip.origin.name}</T>
            <T size={12} color={colors.muted} numberOfLines={1}>{trip.pickup_point}</T>
          </View>
          <View>
            <T size={16} weight="800">{trip.arrival_time} · {trip.destination.name}</T>
            <T size={12} color={colors.muted} numberOfLines={1}>{trip.drop_point}</T>
          </View>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <T testID={`ride-price-${trip.trip_id}`} size={20} weight="800" color={colors.brandPrimary}>{inr(trip.price)}</T>
          <T size={11} color={colors.muted}>{t("ride.per_seat")}</T>
        </View>
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm, alignItems: "center" }}>
        <Badge icon="calendar-outline" label={fmtDate(trip.date)} tone="muted" />
        <Badge icon="time-outline" label={`${fmtDur(trip.duration_min)} · ~${trip.distance_km} km`} tone="muted" />
        <Badge icon="person-outline" label={t("ride.seats_left", { n: trip.seats_available })} tone={trip.seats_available ? "info" : "error"} />
        {trip.instant_booking ? <Badge icon="flash" label={t("trip.instant")} tone="warning" /> : null}
        {trip.match?.type === "along_route" ? <Badge testID={`ride-along-route-${trip.trip_id}`} icon="git-merge-outline" label={t("geo.along_route", { n: trip.match.pickup_km, time: trip.match.pickup_eta ?? "" })} tone="accent" /> : null}
        {trip.is_demo ? <Badge label={t("common.demo")} tone="muted" /> : null}
      </View>
      <View style={{ height: 1, backgroundColor: colors.divider }} />
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <Avatar name={trip.driver?.name} uri={trip.driver?.has_photo ? publicPhoto(trip.driver_id) : trip.driver?.picture} size={44} />
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <T weight="700" numberOfLines={1}>{trip.driver?.name}</T>
            {trip.driver?.driver_status === "approved" ? <Ionicons name="shield-checkmark" size={14} color={colors.success} /> : null}
          </View>
          <Rating value={trip.driver?.rating_avg} count={trip.driver?.rating_count} />
          {trip.driver?.has_photo ? <Badge testID={`ride-photo-badge-${trip.trip_id}`} icon="camera" label={t("v2.verified_photo")} tone="success" /> : null}
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <T size={12} weight="600">{v.make} {v.model}</T>
          <T size={11} color={colors.muted}>{v.ac ? t("ride.ac") : t("ride.nonac")} · {t("ride.luggage")}: {t(`vehicle.${v.luggage}`)}</T>
        </View>
      </View>
    </Card>
  );
}
