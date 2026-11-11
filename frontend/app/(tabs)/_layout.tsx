import Ionicons from "@react-native-vector-icons/ionicons";
import { Tabs, usePathname } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import React, { useEffect, useState } from "react";
import { AppState, Platform, View } from "react-native";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

/** Total unread booking messages for the Messages tab badge (refreshes every 15 s while the app is open). */
function useUnreadMessages() {
  const { user } = useAuth();
  const path = usePathname();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    const load = () => api("/conversations").then((r) => alive && setN(r.items.reduce((s: number, c: any) => s + (c.unread || 0), 0))).catch(() => {});
    load();
    const h = setInterval(() => AppState.currentState === "active" && load(), 15000);
    return () => { alive = false; clearInterval(h); };
  }, [user, path]);
  return n;
}

export default function TabsLayout() {
  const { t } = useI18n();
  const { colors } = useTheme();
  const unread = useUnreadMessages();

  if (usesNativeTabs) {
    return (
      <NativeTabs tintColor={colors.brandPrimary}>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="house.fill" />
          <NativeTabs.Trigger.Label>{t("tab.home")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="offer">
          <NativeTabs.Trigger.Icon sf="plus.circle.fill" />
          <NativeTabs.Trigger.Label>{t("tab.offer")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="bookings">
          <NativeTabs.Trigger.Icon sf="ticket.fill" />
          <NativeTabs.Trigger.Label>{t("tab.bookings")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="messages">
          <NativeTabs.Trigger.Icon sf="bubble.left.and.bubble.right.fill" />
          <NativeTabs.Trigger.Label>{t("v2.messages")}</NativeTabs.Trigger.Label>
          {unread ? <NativeTabs.Trigger.Badge>{String(unread)}</NativeTabs.Trigger.Badge> : null}
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  const icon = (on: any, off: any) =>
    function TabIcon({ color, focused }: { color: any; focused: boolean }) {
      return <Ionicons name={focused ? on : off} size={23} color={color} />;
    };
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontFamily: "PJS-SemiBold", fontSize: 11 },
        tabBarStyle: { backgroundColor: colors.surfaceSecondary, borderTopColor: colors.border, ...(Platform.OS === "web" ? { height: 64 } : {}) },
        tabBarItemStyle: { alignSelf: "center" },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("tab.home"), tabBarButtonTestID: "tab-home", tabBarIcon: icon("home", "home-outline") }} />
      <Tabs.Screen
        name="offer"
        options={{
          title: t("tab.offer"),
          tabBarButtonTestID: "tab-offer",
          tabBarActiveTintColor: colors.brandTertiary,
          tabBarIcon: ({ focused }) => (
            <View style={{ width: 44, height: 44, borderRadius: 22, marginTop: -14, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", borderWidth: 3, borderColor: focused ? colors.brand : colors.surfaceSecondary }}>
              <Ionicons name="add" size={26} color={colors.onBrandTertiary} />
            </View>
          ),
        }}
      />
      <Tabs.Screen name="bookings" options={{ title: t("tab.bookings"), tabBarButtonTestID: "tab-bookings", tabBarIcon: icon("ticket", "ticket-outline") }} />
      <Tabs.Screen name="messages" options={{ title: t("v2.messages"), tabBarButtonTestID: "tab-messages", tabBarIcon: icon("chatbubbles", "chatbubbles-outline"), tabBarBadge: unread ? unread : undefined, tabBarBadgeStyle: { backgroundColor: colors.brandTertiary, color: colors.onBrandTertiary, fontSize: 10 } }} />
    </Tabs>
  );
}
