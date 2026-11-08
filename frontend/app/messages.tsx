import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Avatar, Badge, Card, Empty, Header, Loading, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function MessagesScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const [items, setItems] = useState<any[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(() => api("/conversations").then((r) => setItems(r.items)).catch(() => setItems([])), []);
  useFocusEffect(useCallback(() => { load(); const h = setInterval(load, 8000); return () => clearInterval(h); }, [load]));

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.messages")} />
      {items === null ? <Loading /> : (
        <FlatList
          testID="conversations-list"
          data={items}
          keyExtractor={(c) => c.booking_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
          contentContainerStyle={{ padding: space.lg, gap: space.sm, paddingBottom: insets.bottom + space.xl }}
          ListEmptyComponent={<Empty icon="chatbubbles-outline" title={t("v2.messages_empty")} />}
          renderItem={({ item }) => (
            <Card testID={`conversation-${item.booking_id}`} onPress={() => router.push(`/chat/${item.booking_id}`)} style={{ flexDirection: "row", gap: space.md, alignItems: "center", padding: space.md }}>
              <Avatar name={item.other?.name} uri={item.other?.picture} />
              <View style={{ flex: 1, gap: 2 }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                  <T weight="800" numberOfLines={1} style={{ flex: 1 }}>{item.other?.name}</T>
                  {item.last ? <T size={11} color={colors.muted}>{fmtDate(item.last.created_at, { day: "numeric", month: "short" })}</T> : null}
                </View>
                <T size={12} color={colors.muted} numberOfLines={1}>{item.kind === "hire" ? `${t("v2.hire")} · ` : ""}{item.booking_id} · {item.route}</T>
                <T size={13} numberOfLines={1} weight={item.unread ? "700" : "400"}>{item.last ? (item.last.sender_id === "system" ? t(`notif.${item.last.sys_type}`, item.last.params) : item.last.text) : t("chat.empty")}</T>
              </View>
              {item.unread ? <Badge testID={`unread-${item.booking_id}`} label={String(item.unread)} tone="accent" /> : null}
            </Card>
          )}
        />
      )}
    </View>
  );
}
