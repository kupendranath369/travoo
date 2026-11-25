import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, pictureUrl } from "@/src/api";
import { useAuth } from "@/src/auth";
import { LocalDriverDashboard } from "@/src/components/localdriver/Dashboard";
import { float, PRO_STATUS } from "@/src/components/localdriver/parts";
import { Avatar, Badge, Btn, IconName, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

function Option({ icon, tint, title, desc, on, onPress, testID }: { icon: IconName; tint: string; title: string; desc: string; on: boolean; onPress: () => void; testID: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} role="checkbox" aria-checked={on} onPress={onPress} style={({ pressed }) => [float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md,
      borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 2, borderColor: on ? colors.brandPrimary : "transparent", transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
      <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={28} color={tint} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <T weight="800" size={15}>{title}</T>
        <T size={12} color={colors.muted}>{desc}</T>
      </View>
      <Ionicons name={on ? "checkbox" : "square-outline"} size={26} color={on ? colors.brandPrimary : colors.borderStrong} />
    </Pressable>
  );
}

/** Driver-mode home: dashboard once approved, otherwise "Become a Travoo Driver" service selection / status. */
export function DriverHome() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const [me, setMe] = useState<any>(null);
  const [pick, setPick] = useState<string[]>(["rent"]);
  const load = useCallback(() => api("/pro/me").then(setMe).catch(() => setMe({ profile: null })), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const p = me?.profile;
  if (p?.status === "approved") return <LocalDriverDashboard embedded />;
  const st = p ? PRO_STATUS[p.status] ?? PRO_STATUS.under_review : null;
  const toggle = (k: string) => setPick(pick.includes(k) ? pick.filter((x) => x !== k) : [...pick, k]);
  const next = () => {
    const local = pick.filter((k) => k !== "carpool");
    if (local.length) return router.push(`/hire/register?service=${local.length === 2 ? "both" : local[0]}`);
    router.push("/driver");
  };
  return (
    <ScrollView testID="driver-home" refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      contentContainerStyle={{ padding: space.lg, paddingTop: insets.top + space.md, gap: space.lg, paddingBottom: insets.bottom + 120 }}>
      <Pressable testID="driver-home-profile" onPress={() => router.push("/profile")} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <Avatar name={user?.name ?? ""} uri={pictureUrl(user?.picture)} size={48} />
        <T size={20} weight="800" style={{ flex: 1 }}>Hi, {user?.name?.split(" ")[0]}</T>
        <Badge testID="driver-home-mode" label="Driver Mode" tone="info" />
      </Pressable>
      {!me ? null : !p ? (
        <>
          <View style={{ gap: 4 }}>
            <T size={26} weight="800" color={colors.brandSecondary}>Become a Travoo Driver</T>
            <T size={14} color={colors.muted}>Choose the services you want to provide.</T>
          </View>
          <Option testID="driver-choose-carpool" icon="people" tint={colors.brandPrimary} title="Offer a Ride" desc="Share your trip and travel together (Carpool)" on={pick.includes("carpool")} onPress={() => toggle("carpool")} />
          <Option testID="driver-choose-rent" icon="person" tint={colors.brandSecondary} title="Driver Only" desc="Drive a customer's own car (Rent a Driver)" on={pick.includes("rent")} onPress={() => toggle("rent")} />
          <Option testID="driver-choose-book" icon="car-sport" tint={colors.brandTertiary} title="Car with Driver" desc="Provide your car with driving service (Book a Driver)" on={pick.includes("book")} onPress={() => toggle("book")} />
          <Btn testID="driver-choose-continue" icon="arrow-forward" label="Continue" disabled={!pick.length} onPress={next} />
        </>
      ) : (
        <Pressable testID="driver-registration-status" onPress={() => router.push("/hire/register")} style={[float, { gap: space.sm, padding: space.lg, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }]}>
          <T size={18} weight="800">Local driver registration</T>
          <Badge label={st!.label} tone={st!.tone} />
          <T size={13} color={colors.muted}>{st!.text}</T>
        </Pressable>
      )}
      {me ? (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          <Btn small style={{ flex: 1 }} testID="driver-offer-ride" variant="outline" icon="add-circle-outline" label="Offer" onPress={() => router.push("/offer")} />
          <Btn small style={{ flex: 1 }} testID="driver-carpool-verify" variant="outline" icon="shield-checkmark-outline" label="Verify" onPress={() => router.push("/driver")} />
        </View>
      ) : null}
    </ScrollView>
  );
}
