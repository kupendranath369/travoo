import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { MyRideCard } from "@/src/components/MyRideCard";
import { Btn, Empty, ErrorBox, Loading, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

export default function MyRidesScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setErr("");
    try { setRows(await api("/trips/mine")); } catch (e: any) { setErr(e.message); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, paddingBottom: space.md, paddingHorizontal: space.lg, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <T testID="my-rides-title" size={22} weight="800">My Rides</T>
        <T size={13} color={colors.muted}>Rides you have offered</T>
      </View>
      {err ? <ErrorBox message={err} onRetry={load} /> : rows === null ? <Loading /> : (
        <FlatList
          testID="my-rides-list"
          data={rows}
          keyExtractor={(i) => i.trip_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
          contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
          ListEmptyComponent={<Empty icon="car-outline" title={t("bookings.rides_empty")} action={<Btn testID="my-rides-offer-button" icon="add-circle-outline" label="Offer a ride" onPress={() => router.push("/offer")} style={{ marginTop: space.md, alignSelf: "stretch" }} />} />}
          renderItem={({ item }) => <MyRideCard item={item} />}
        />
      )}
    </View>
  );
}
