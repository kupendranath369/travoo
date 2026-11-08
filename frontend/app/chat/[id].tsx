import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, Pressable, TextInput, View } from "react-native";
import { KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Avatar, Empty, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { user } = useAuth();
  const [msgs, setMsgs] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const list = useRef<FlatList>(null);

  const load = useCallback(async () => {
    try {
      setMsgs(await api(`/bookings/${id}/messages`));
    } catch (e: any) {
      setErr(e.message);
    }
  }, [id]);
  useEffect(() => {
    load();
    const h = setInterval(load, 3000);
    return () => clearInterval(h);
  }, [load]);

  const send = async () => {
    const v = text.trim();
    if (!v) return;
    setText("");
    try {
      const m = await api(`/bookings/${id}/messages`, { body: { text: v } });
      setMsgs((p) => [...p, m]);
      setErr("");
    } catch (e: any) {
      setErr(e.message);
      setText(v);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={`${t("chat.title")} · ${id}`} />
      <FlatList
        ref={list}
        testID="chat-messages-list"
        data={msgs}
        keyExtractor={(m) => m.message_id}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={{ padding: space.lg, gap: space.sm, flexGrow: 1 }}
        ListEmptyComponent={<Empty icon="chatbubbles-outline" title={t("chat.empty")} />}
        renderItem={({ item }) => {
          if (item.sender_id === "system")
            return (
              <View testID={`system-message-${item.message_id}`} style={{ alignSelf: "center", backgroundColor: colors.brandSoft, borderRadius: 12, paddingHorizontal: space.md, paddingVertical: 6, maxWidth: "90%" }}>
                <T size={12} weight="600" color={colors.brandPrimary} center>{t(`notif.${item.sys_type}`, item.params)}</T>
              </View>
            );
          const mine = item.sender_id === user?.user_id;
          return (
            <View style={{ flexDirection: "row", gap: space.sm, alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "85%", alignItems: "flex-end" }}>
              {!mine ? <Avatar name={item.sender_name} uri={item.sender_picture} size={28} /> : null}
            <View style={{ flexShrink: 1, backgroundColor: mine ? colors.brandPrimary : colors.surfaceSecondary, borderRadius: 16, padding: space.md, borderWidth: mine ? 0 : 1, borderColor: colors.border }}>
              {!mine ? <T size={11} weight="700" color={colors.muted}>{item.sender_name}</T> : null}
              <T color={mine ? colors.onBrandPrimary : colors.onSurface}>{item.text}</T>
              <T size={10} color={mine ? colors.onBrandPrimary : colors.muted} style={{ opacity: 0.8, alignSelf: "flex-end" }}>
                {new Date(item.created_at.endsWith("Z") ? item.created_at : `${item.created_at}Z`).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                {mine ? `  ${item.status === "read" ? "✓✓ " + t("v2.read") : "✓ " + t("v2.delivered")}` : ""}
              </T>
            </View>
            </View>
          );
        }}
      />
      {err ? <T testID="chat-error" size={12} color={colors.error} style={{ paddingHorizontal: space.lg }}>{err}</T> : null}
      <KeyboardStickyView offset={{ opened: insets.bottom }}>
        <View style={{ flexDirection: "row", gap: space.sm, padding: space.md, paddingBottom: insets.bottom + space.md, backgroundColor: colors.surfaceSecondary, borderTopWidth: 1, borderTopColor: colors.border }}>
          <TextInput testID="chat-input" value={text} onChangeText={setText} placeholder={t("chat.ph")} placeholderTextColor={colors.muted} multiline style={{ flex: 1, minHeight: 44, maxHeight: 120, borderRadius: 22, paddingHorizontal: space.lg, paddingTop: 12, backgroundColor: colors.surfaceTertiary, color: colors.onSurface, fontSize: 15 }} />
          <Pressable testID="chat-send-button" onPress={send} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="send" size={18} color={colors.onBrandPrimary} />
          </Pressable>
        </View>
      </KeyboardStickyView>
    </View>
  );
}
