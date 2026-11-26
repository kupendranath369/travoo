import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, View } from "react-native";

import { api } from "@/src/api";
import { useTheme } from "@/src/theme";

/** Top-right bell that opens Notifications; gold dot when something is unread. */
export function NotificationBell({ testID = "notifications-bell" }: { testID?: string }) {
  const { colors } = useTheme();
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  useFocusEffect(useCallback(() => { api("/notifications").then((n) => setUnread(n.unread || 0)).catch(() => {}); }, []));
  return (
    <Pressable testID={testID} accessibilityLabel="Notifications" onPress={() => router.push("/notifications")} hitSlop={6}
      style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
      <Ionicons name="notifications-outline" size={20} color={colors.brand} />
      {unread ? <View testID={`${testID}-dot`} style={{ position: "absolute", top: 7, right: 8, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.brandTertiary }} /> : null}
    </Pressable>
  );
}
