import Ionicons from "@react-native-vector-icons/ionicons";
import React from "react";
import { View } from "react-native";

import { Btn, Card, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

function Stars({ value, size = 14 }: { value: number; size?: number }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Ionicons key={i} name={value >= i ? "star" : value >= i - 0.5 ? "star-half" : "star-outline"} size={size} color={colors.brandTertiary} />
      ))}
    </View>
  );
}

/** Driver's star rating + latest reviews, shown to riders before they book. */
export function DriverReviews({ avg, count, reviews, onSeeAll }: { avg?: number; count?: number; reviews: any[]; onSeeAll: () => void }) {
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  return (
    <Card testID="driver-reviews-card" style={{ gap: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <T testID="driver-rating-avg" size={32} weight="800">{count ? (avg ?? 0).toFixed(1) : "–"}</T>
        <View style={{ flex: 1, gap: 2 }}>
          <Stars value={count ? avg ?? 0 : 0} size={18} />
          <T testID="driver-rating-count" size={12} color={colors.muted}>{count ? t("rev.count", { n: count }) : t("rev.none")}</T>
        </View>
      </View>
      {reviews.map((r) => (
        <View key={r.review_id} testID={`driver-review-${r.review_id}`} style={{ gap: 4, borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: space.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.sm }}>
            <T weight="700" numberOfLines={1} style={{ flex: 1 }}>{r.reviewer_name}</T>
            <Stars value={r.rating} size={12} />
          </View>
          {r.comment ? <T size={13}>{r.comment}</T> : null}
          <T size={11} color={colors.muted}>{[r.route, r.created_at ? fmtDate(r.created_at, { day: "numeric", month: "short", year: "numeric" }) : ""].filter(Boolean).join(" · ")}</T>
        </View>
      ))}
      {count && count > reviews.length ? <Btn small variant="ghost" testID="driver-reviews-see-all" label={t("rev.see_all", { n: count })} onPress={onSeeAll} /> : null}
    </Card>
  );
}
