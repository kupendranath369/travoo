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

function Choice({ icon, title, desc, onPress, testID }: { icon: IconName; title: string; desc: string; onPress: () => void; testID: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [float, { flex: 1, minHeight: 170, padding: space.md, gap: space.sm, borderRadius: radius.lg,
      backgroundColor: colors.surfaceSecondary, transform: [{ scale: pressed ? 0.97 : 1 }] }]}>
      <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={24} color="#fff" />
      </View>
      <T weight="800" size={15}>{title}</T>
      <T size={12} color={colors.muted}>{desc}</T>
      <T size={12} weight="800" color={colors.brandTertiary}>Register →</T>
    </Pressable>
  );
}

/** Home for users in Driver mode: local driver registration choice / status / dashboard, plus carpool. */
export function DriverHome() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const [me, setMe] = useState<any>(null);
  const load = useCallback(() => api("/pro/me").then(setMe).catch(() => setMe({ profile: null })), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const p = me?.profile;
  if (p?.status === "approved") return <LocalDriverDashboard embedded />;
  const st = p ? PRO_STATUS[p.status] ?? PRO_STATUS.under_review : null;
  return (
    <ScrollView testID="driver-home" refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      contentContainerStyle={{ padding: space.lg, paddingTop: insets.top + space.lg, gap: space.lg, paddingBottom: insets.bottom + 120 }}>
      <Pressable testID="driver-home-profile" onPress={() => router.push("/profile")} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <Avatar name={user?.name ?? ""} uri={pictureUrl(user?.picture)} size={48} />
        <View style={{ flex: 1 }}>
          <T size={18} weight="800">Hi, {user?.name?.split(" ")[0]}</T>
          <Badge testID="driver-home-mode" icon="car-sport" label="Driver mode" tone="info" />
        </View>
      </Pressable>

      <T size={22} weight="800">Local Driver</T>
      {!me ? null : !p ? (
        <>
          <T size={13} color={colors.muted}>Choose how you want to work. You can add the other service later.</T>
          <View style={{ flexDirection: "row", gap: space.md }}>
            <Choice testID="driver-choose-rent" icon="key-outline" title="Rented driver only" desc="Drive the customer's own car. No vehicle needed." onPress={() => router.push("/hire/register?service=rent")} />
            <Choice testID="driver-choose-book" icon="car-sport-outline" title="Book car + driver" desc="Provide your own car and drive the customer." onPress={() => router.push("/hire/register?service=book")} />
          </View>
        </>
      ) : p.status === "approved" ? (
        <Pressable testID="driver-open-dashboard" onPress={() => router.push("/hire/driver")} style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.lg,
          borderRadius: radius.lg, backgroundColor: p.online ? colors.success : colors.brandTertiary }]}>
          <Ionicons name="speedometer-outline" size={30} color="#fff" />
          <View style={{ flex: 1 }}>
            <T size={18} weight="800" color="#fff">Driver Dashboard</T>
            <T size={12} color="#fff">{p.online ? "You're Online" : "You're Offline · tap to go online"} · {(p.services ?? []).map((s: string) => (s === "book" ? "Book" : "Rent")).join(" + ")}</T>
          </View>
          <Ionicons name="chevron-forward" size={22} color="#fff" />
        </Pressable>
      ) : (
        <Pressable testID="driver-registration-status" onPress={() => router.push("/hire/register")} style={[float, { gap: space.sm, padding: space.lg, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }]}>
          <Badge label={st!.label} tone={st!.tone} />
          <T size={13} color={colors.muted}>{st!.text}</T>
        </Pressable>
      )}

      <T size={18} weight="800">Carpool</T>
      <View style={{ flexDirection: "row", gap: space.md }}>
        <Btn style={{ flex: 1 }} testID="driver-offer-ride" variant="outline" icon="add-circle-outline" label="Offer a ride" onPress={() => router.push("/offer")} />
        <Btn style={{ flex: 1 }} testID="driver-carpool-verify" variant="outline" icon="shield-checkmark-outline" label="Verify" onPress={() => router.push("/driver")} />
      </View>
      <View style={{ flexDirection: "row", gap: space.md }}>
        <Btn style={{ flex: 1 }} small testID="driver-messages" variant="ghost" icon="chatbubbles-outline" label="Messages" onPress={() => router.push("/messages")} />
        <Btn style={{ flex: 1 }} small testID="driver-notifications" variant="ghost" icon="notifications-outline" label="Alerts" onPress={() => router.push("/notifications")} />
      </View>
    </ScrollView>
  );
}
