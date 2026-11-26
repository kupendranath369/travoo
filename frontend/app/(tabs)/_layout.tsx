import Ionicons from "@react-native-vector-icons/ionicons";
import { Tabs, usePathname } from "expo-router";
import { NativeTabs } from "expo-router/native-tabs";
import React, { useEffect, useState } from "react";
import { AppState, Platform, View } from "react-native";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { RoleChooser } from "@/src/components/RoleChooser";
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

const DRIVER_TABS = ["index", "driver-trips", "driver-earnings", "messages", "notifications"];
const PASSENGER_TABS = ["index", "bookings", "offer", "messages", "notifications"];

export default function TabsLayout() {
  const { t } = useI18n();
  const { user } = useAuth();
  const driver = user?.account_type === "driver";
  const shown = (name: string) => (driver ? DRIVER_TABS : PASSENGER_TABS).includes(name);
  // hide the other mode's tabs from the bar but keep their routes reachable (e.g. Messages from the driver dashboard)
  const hide = (name: string) => (shown(name) ? {} : { tabBarButton: () => null, tabBarItemStyle: { display: "none" as const } });
  const { colors } = useTheme();
  const unread = useUnreadMessages();
  const path = usePathname();
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [openRequests, setOpenRequests] = useState(0);

  useEffect(() => {
    const loadNotifications = async () => {
      try {
        const n = await api("/notifications");
        setUnreadNotifications(n.unread || 0);
      } catch (e) {
        setUnreadNotifications(0);
      }
    };
    const loadRequests = () => { if (driver) api("/hire/requests").then((r) => setOpenRequests((r.inbox ?? []).filter((x: any) => x.status === "open" && !x.dispatch?.response).length)).catch(() => {}); };
    loadNotifications();
    loadRequests();
    const interval = setInterval(() => { loadNotifications(); loadRequests(); }, 15000);
    return () => clearInterval(interval);
  }, [driver, path]);

  if (usesNativeTabs) {
    return (
      <>
      <RoleChooser visible={user?.mode_chosen === false} />
      <NativeTabs tintColor={colors.brandPrimary}>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="house.fill" />
          <NativeTabs.Trigger.Label>{t("tab.home")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="driver-requests" hidden>
          <NativeTabs.Trigger.Icon sf="bell.badge.fill" />
          <NativeTabs.Trigger.Label>Requests</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="driver-trips" hidden={!driver}>
          <NativeTabs.Trigger.Icon sf="car.fill" />
          <NativeTabs.Trigger.Label>My Trips</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="driver-earnings" hidden={!driver}>
          <NativeTabs.Trigger.Icon sf="indianrupeesign.circle.fill" />
          <NativeTabs.Trigger.Label>Earnings</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="bookings" hidden={driver}>
          <NativeTabs.Trigger.Icon sf="ticket.fill" />
          <NativeTabs.Trigger.Label>{t("tab.bookings")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="offer" hidden={driver}>
          <NativeTabs.Trigger.Icon sf="plus.circle.fill" />
          <NativeTabs.Trigger.Label>Offer Ride</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="messages">
          <NativeTabs.Trigger.Icon sf="bubble.left.and.bubble.right.fill" />
          <NativeTabs.Trigger.Label>{t("v2.messages")}</NativeTabs.Trigger.Label>
          {unread ? <NativeTabs.Trigger.Badge>{String(unread)}</NativeTabs.Trigger.Badge> : null}
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="notifications">
          <NativeTabs.Trigger.Icon sf="bell.fill" />
          <NativeTabs.Trigger.Label>{t("profile.notifications")}</NativeTabs.Trigger.Label>
          {unreadNotifications ? <NativeTabs.Trigger.Badge>{String(unreadNotifications)}</NativeTabs.Trigger.Badge> : null}
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="account" hidden>
          <NativeTabs.Trigger.Icon sf="person.crop.circle" />
          <NativeTabs.Trigger.Label>Account</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
      </NativeTabs>
      </>
    );
  }

  const icon = (on: any, off: any) =>
    function TabIcon({ color, focused }: { color: any; focused: boolean }) {
      return <Ionicons name={focused ? on : off} size={23} color={color} />;
    };
  return (
    <>
    <RoleChooser visible={user?.mode_chosen === false} />
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontFamily: "PJS-SemiBold", fontSize: 11 },
          tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border, ...(Platform.OS === "web" ? { height: 68 } : {}) },
        tabBarItemStyle: { alignSelf: "center" },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("tab.home"), tabBarButtonTestID: "tab-home", tabBarIcon: icon("home", "home-outline") }} />
      <Tabs.Screen name="driver-requests" options={{ ...hide("driver-requests"), title: "Requests", tabBarButtonTestID: "tab-requests", tabBarIcon: icon("notifications", "notifications-outline"), tabBarBadge: openRequests || undefined, tabBarBadgeStyle: { backgroundColor: colors.brandTertiary, color: colors.onBrandTertiary, fontSize: 10 } }} />
      <Tabs.Screen name="driver-trips" options={{ ...hide("driver-trips"), title: "My Trips", tabBarButtonTestID: "tab-trips", tabBarIcon: icon("car", "car-outline") }} />
      <Tabs.Screen name="driver-earnings" options={{ ...hide("driver-earnings"), title: "Earnings", tabBarButtonTestID: "tab-earnings", tabBarIcon: icon("wallet", "wallet-outline") }} />
      <Tabs.Screen name="bookings" options={{ ...hide("bookings"), title: t("tab.bookings"), tabBarButtonTestID: "tab-bookings", tabBarIcon: icon("ticket", "ticket-outline") }} />
      <Tabs.Screen name="offer" options={{ ...hide("offer"), title: "Offer Ride", tabBarButtonTestID: "tab-offer", tabBarIcon: icon("add-circle", "add-circle-outline") }} />
      <Tabs.Screen name="messages" options={{ ...hide("messages"), title: t("v2.messages"), tabBarButtonTestID: "tab-messages", tabBarIcon: icon("chatbubbles", "chatbubbles-outline"), tabBarBadge: unread ? unread : undefined, tabBarBadgeStyle: { backgroundColor: colors.brandTertiary, color: colors.onBrandTertiary, fontSize: 10 } }} />
      <Tabs.Screen name="notifications" options={{ ...hide("notifications"), title: t("profile.notifications"), tabBarButtonTestID: "tab-notifications", tabBarIcon: icon("notifications", "notifications-outline"), tabBarBadge: unreadNotifications ? unreadNotifications : undefined, tabBarBadgeStyle: { backgroundColor: colors.brandTertiary, color: colors.onBrandTertiary, fontSize: 10 } }} />
      <Tabs.Screen name="account" options={{ ...hide("account"), title: "Account", tabBarButtonTestID: "tab-account", tabBarIcon: icon("person-circle", "person-circle-outline") }} />
    </Tabs>
    </>
  );
}
