import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams } from "expo-router";
import React, { useEffect, useState } from "react";
import { Linking, ScrollView, Share, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Field, Header, Section, T, space, statusTone } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function SupportScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const toast = useToast();
  const p = useLocalSearchParams<{ tab?: string; type?: string; booking?: string; user?: string }>();
  const [type, setType] = useState<string>(p.type || (p.tab === "sos" ? "sos" : "complaint"));
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [mine, setMine] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = () => api("/tickets/mine").then(setMine).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      await api("/tickets", { body: { type, subject, message, booking_id: p.booking || null, reported_user_id: p.user || null } });
      toast(t("support.sent"));
      setSubject("");
      setMessage("");
      load();
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("support.title")} />
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card testID="sos-card" style={{ borderColor: colors.error, gap: space.md }}>
          <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
            <Ionicons name="warning" size={24} color={colors.error} />
            <T weight="800" size={16}>{t("sos.title")}</T>
          </View>
          <T size={13}>{t("sos.body")}</T>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Btn small style={{ flex: 1 }} variant="danger" icon="call" label={t("sos.call")} onPress={() => Linking.openURL("tel:112")} testID="sos-call-button" />
            <Btn small style={{ flex: 1 }} variant="outline" icon="share-social" label={t("sos.share")} onPress={() => Share.share({ message: `Travoo trip ${p.booking ?? ""} — I am travelling with Travoo. Booking: ${p.booking ?? "n/a"}` })} testID="sos-share-button" />
          </View>
        </Card>

        <Section title={t("safety.title")}>
          <Card style={{ gap: space.sm }}>
            {[1, 2, 3, 4].map((i) => (
              <View key={i} style={{ flexDirection: "row", gap: space.sm }}>
                <Ionicons name="shield-checkmark-outline" size={18} color={colors.success} />
                <T size={13} style={{ flex: 1 }}>{t(`safety.${i}`)}</T>
              </View>
            ))}
          </Card>
        </Section>

        <Section title={t("support.submit")}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {["complaint", "report_user", "question", "sos"].map((k) => (
              <Chip key={k} testID={`ticket-type-${k}`} label={k === "sos" ? t("booking.sos") : t(`support.${k}`)} active={type === k} onPress={() => setType(k)} />
            ))}
          </ScrollView>
          {p.booking ? <Badge label={`${t("booking.id")}: ${p.booking}`} tone="muted" /> : null}
          <Field testID="ticket-subject-input" label={t("support.subject")} value={subject} onChangeText={setSubject} />
          <Field testID="ticket-message-input" label={t("support.message")} value={message} onChangeText={setMessage} multiline />
          {err ? <T testID="ticket-error" color={colors.error}>{err}</T> : null}
          <Btn testID="ticket-submit-button" label={t("support.submit")} onPress={submit} loading={busy} />
          <T size={12} color={colors.muted}>{t("support.grievance")}</T>
        </Section>

        {mine.length ? (
          <Section title={t("support.my_tickets")}>
            {mine.map((m) => (
              <Card key={m.ticket_id} testID={`my-ticket-${m.ticket_id}`} style={{ gap: 4, padding: space.md }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <T weight="700">{m.ticket_id} · {m.subject}</T>
                  <Badge label={m.status} tone={m.status === "resolved" ? "success" : statusTone("pending")} />
                </View>
                <T size={12} color={colors.muted}>{fmtDate(m.created_at)}</T>
              </Card>
            ))}
          </Section>
        ) : null}
      </KeyboardAwareScrollView>
    </View>
  );
}
