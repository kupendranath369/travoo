import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { LocationField } from "@/src/components/LocationField";
import { RideCard } from "@/src/components/RideCard";
import { Card, Chip, Empty, ErrorBox, Loading, Stepper, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const PRICE_CAPS = [300, 500, 800, 1200];

export default function SearchScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const p = useLocalSearchParams<{ from?: string; to?: string; date?: string; seats?: string }>();
  const [from, setFrom] = useState<Loc | null>(null);
  const [to, setTo] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [seats, setSeats] = useState(1);
  const [sort, setSort] = useState<"early" | "price" | "rating">("early");
  const [ac, setAc] = useState(false);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [res, setRes] = useState<{ trips: any[]; alternative_dates: any[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(true);
  const [marked, setMarked] = useState<Set<string>>(new Set());
  const router = useRouter();

  useEffect(() => {
    if (p.from && p.to) {
      setFrom(JSON.parse(p.from));
      setTo(JSON.parse(p.to));
      setDate(p.date || null);
      setSeats(Number(p.seats || 1));
      setEditing(false);
    }
  }, [p.from, p.to, p.date, p.seats]);

  const run = useCallback(async () => {
    if (!from || !to) return;
    setLoading(true);
    setErr("");
    try {
      const q = new URLSearchParams({ from_lat: String(from.lat), from_lng: String(from.lng), to_lat: String(to.lat), to_lng: String(to.lng), seats: String(seats), sort, ac: String(ac) });
      if (date) q.set("date", date);
      if (maxPrice) q.set("max_price", String(maxPrice));
      const r = await api(`/trips/search?${q}`);
      setRes(r);
      setMarked(new Set(r.available_dates.map((a: any) => a.date)));
      api("/searches", { body: { kind: "intercity", origin: locPayload(from), destination: locPayload(to), date, seats } }).catch(() => {});
    } catch (e: any) {
      setErr(e.message);
    }
    setLoading(false);
  }, [from, to, date, seats, sort, ac, maxPrice]);

  useEffect(() => {
    if (!editing) run();
  }, [run, editing]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        {editing ? (
          <View style={{ paddingHorizontal: space.lg, paddingBottom: space.md }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, marginBottom: space.xs }}>
              <Pressable testID="search-edit-back-button" accessibilityLabel={t("common.back")} hitSlop={8} onPress={() => (from && to && res ? setEditing(false) : router.canGoBack() ? router.back() : router.replace("/"))} style={{ width: 36, height: 44, justifyContent: "center" }}>
                <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
              </Pressable>
              <T size={22} weight="800">{t("search.title")}</T>
            </View>
            <LocationField testID="search-from-field" label={t("search.from")} value={from} onChange={setFrom} icon="radio-button-on" />
            <LocationField testID="search-to-field" label={t("search.to")} value={to} onChange={setTo} icon="location" />
            <DateField testID="search-date" label={t("search.date")} value={date} onChange={setDate} allowClear marked={marked} />
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: space.sm }}>
              <T weight="600">{t("search.passengers")}</T>
              <Stepper testID="search-passengers" value={seats} onChange={setSeats} />
            </View>
            <Pressable testID="search-submit-button" disabled={!from || !to} onPress={() => { if (editing) setEditing(false); else run(); }} style={{ height: 50, borderRadius: 25, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", opacity: from && to ? 1 : 0.5, flexDirection: "row", gap: space.sm }}>
              <Ionicons name="search" size={18} color={colors.onBrandPrimary} />
              <T weight="700" color={colors.onBrandPrimary}>{t("btn.find")}</T>
            </Pressable>
            <Pressable testID="search-hire-link" onPress={() => router.push("/hire")} style={{ flexDirection: "row", gap: space.sm, alignItems: "center", justifyContent: "center", paddingTop: space.md }}>
              <Ionicons name="key-outline" size={16} color={colors.brandTertiary} />
              <T weight="700" color={colors.brandTertiary}>{t("v2.hire")} · {t("v2.hire_d")}</T>
            </Pressable>
          </View>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", paddingLeft: space.sm, marginBottom: space.sm }}>
          <Pressable testID="search-back-button" accessibilityLabel={t("common.back")} hitSlop={8} onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
          </Pressable>
          <Pressable testID="search-summary" onPress={() => setEditing(true)} style={{ flex: 1, marginRight: space.lg, padding: space.md, borderRadius: 14, backgroundColor: colors.surfaceTertiary, flexDirection: "row", alignItems: "center", gap: space.md }}>
            <Ionicons name="navigate-outline" size={18} color={colors.brandPrimary} />
            <View style={{ flex: 1 }}>
              <T weight="800" numberOfLines={1}>{from?.name} → {to?.name}</T>
              <T size={12} color={colors.muted}>{date ? fmtDate(date) : t("search.any_date")} · {seats} {t("search.passengers")}</T>
            </View>
            <Ionicons name="create-outline" size={18} color={colors.muted} />
          </Pressable>
          </View>
        )}
        {!editing ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ height: 56, flexGrow: 0 }} contentContainerStyle={{ gap: space.sm, paddingHorizontal: space.lg, alignItems: "center", justifyContent: "center" }}>
            <Chip testID="sort-early" icon="time-outline" label={t("sort.early")} active={sort === "early"} onPress={() => setSort("early")} />
            <Chip testID="sort-price" icon="pricetag-outline" label={t("sort.price")} active={sort === "price"} onPress={() => setSort("price")} />
            <Chip testID="sort-rating" icon="star-outline" label={t("sort.rating")} active={sort === "rating"} onPress={() => setSort("rating")} />
            <Chip testID="filter-ac" icon="snow-outline" label={t("filter.ac")} active={ac} onPress={() => setAc(!ac)} />
            {PRICE_CAPS.map((c) => (
              <Chip key={c} testID={`filter-max-${c}`} label={`${t("filter.maxprice")} ${inr(c)}`} active={maxPrice === c} onPress={() => setMaxPrice(maxPrice === c ? null : c)} />
            ))}
          </ScrollView>
        ) : null}
      </View>
      {editing ? null : loading ? (
        <Loading />
      ) : err ? (
        <ErrorBox message={err} onRetry={run} />
      ) : (
        <FlatList
          testID="search-results-list"
          data={res?.trips ?? []}
          keyExtractor={(i) => i.trip_id}
          contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}
          ListHeaderComponent={res?.trips.length ? <T testID="search-results-count" weight="700" color={colors.muted}>{t("search.results", { n: res.trips.length })}</T> : undefined}
          renderItem={({ item }) => <RideCard trip={item} seats={seats} />}
          ListEmptyComponent={
            <View>
              <Empty icon="car-outline" title={date ? t("search.none") : t("search.none_any")} />
              {res?.alternative_dates.length ? (
                <Card style={{ gap: space.sm }}>
                  <T weight="700">{t("search.alt")}</T>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
                    {res.alternative_dates.map((a) => (
                      <Chip key={a.date} testID={`alt-date-${a.date}`} label={`${fmtDate(a.date)} (${a.count})`} onPress={() => setDate(a.date)} />
                    ))}
                  </ScrollView>
                </Card>
              ) : null}
            </View>
          }
        />
      )}
    </View>
  );
}
