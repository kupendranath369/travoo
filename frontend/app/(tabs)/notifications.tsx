import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Card, Empty, Header, Loading, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const ICON: Record<string, any> = { booking_request: "hand-left", booking_confirmed: "checkmark-circle", new_booking: "ticket", booking_rejected: "close-circle", booking_cancelled: "close-circle", trip_cancelled: "close-circle", trip_started: "play-circle", trip_completed: "flag", new_message: "chatbubble", driver_approved: "shield-checkmark", driver_rejected: "alert-circle" };

export default function NotificationsScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const [items, setItems] = useState<any[] | null>(null);

  useFocusEffect(
    useCallback(() => {
      api("/notifications").then((r) => { setItems(r.items); api("/notifications/read", { method: "POST" }).catch(() => {}); }).catch(() => setItems([]));
    }, []),
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("notif.title")} />
      {items === null ? (
        <Loading />
      ) : (
        <FlatList
          testID="notifications-list"
          data={items}
          keyExtractor={(n) => n.notif_id}
          contentContainerStyle={{ padding: space.lg, gap: space.sm, paddingBottom: insets.bottom + space.xl }}
          ListEmptyComponent={<Empty icon="notifications-off-outline" title={t("notif.empty")} />}
          renderItem={({ item }) => (
            <Card testID={`notification-${item.notif_id}`} onPress={() => item.ref && router.push(item.type === "new_message" ? `/chat/${item.ref}` : item.ref.startsWith("LHR-") ? "/hire/requests" : item.ref.startsWith("HIR-") ? `/hire/${item.ref}` : `/booking/${item.ref}`)} style={{ flexDirection: "row", gap: space.md, alignItems: "center", padding: space.md, borderColor: item.read ? colors.border : colors.brandPrimary }}>
              <Ionicons name={ICON[item.type] ?? "notifications"} size={22} color={colors.brandPrimary} />
              <View style={{ flex: 1 }}>
                <T weight={item.read ? "500" : "700"}>{t(`notif.${item.type}`, item.params)}</T>
                <T size={11} color={colors.muted}>{fmtDate(item.created_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</T>
              </View>
            </Card>
          )}
        />
      )}
    </View>
  );
}
