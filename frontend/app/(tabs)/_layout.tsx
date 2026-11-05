import Ionicons from "@react-native-vector-icons/ionicons";
import { Tabs } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import React from "react";
import { Platform, View } from "react-native";

import { useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

export default function TabsLayout() {
  const { t } = useI18n();
  const { colors } = useTheme();

  if (usesNativeTabs) {
    return (
      <NativeTabs tintColor={colors.brandPrimary}>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="house.fill" />
          <NativeTabs.Trigger.Label>{t("tab.home")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="search">
          <NativeTabs.Trigger.Icon sf="magnifyingglass" />
          <NativeTabs.Trigger.Label>{t("tab.search")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="offer">
          <NativeTabs.Trigger.Icon sf="plus.circle.fill" />
          <NativeTabs.Trigger.Label>{t("tab.offer")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="bookings">
          <NativeTabs.Trigger.Icon sf="ticket.fill" />
          <NativeTabs.Trigger.Label>{t("tab.bookings")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="profile">
          <NativeTabs.Trigger.Icon sf="person.crop.circle" />
          <NativeTabs.Trigger.Label>{t("tab.profile")}</NativeTabs.Trigger.Label>
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
      <Tabs.Screen name="search" options={{ title: t("tab.search"), tabBarButtonTestID: "tab-search", tabBarIcon: icon("search", "search-outline") }} />
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
      <Tabs.Screen name="profile" options={{ title: t("tab.profile"), tabBarButtonTestID: "tab-profile", tabBarIcon: icon("person-circle", "person-circle-outline") }} />
    </Tabs>
  );
}
