import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { useLocalSearchParams } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import React, { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { adminApi, adminFileUrl } from "@/src/adminApi";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, ErrorBox, Field, Header, Loading, Section, T, radius, space, statusTone } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function AdminDriverDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [preview, setPreview] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr("");
    try {
      setD(await adminApi(`/admin/drivers/${id}/detail`));
    } catch (e: any) {
      setErr(e.message);
    }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const act = async (key: string, path: string, body: any) => {
    setBusy(key);
    try {
      await adminApi(path, { body });
      toast("Saved");
      setNote("");
      await load();
    } catch (e: any) {
      toast(e.message, "error");
    }
    setBusy("");
  };

  if (err) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title="Driver review" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title="Driver review" /><Loading /></View>;
  const u = d.user, doc = d.documents || {};
  const status = u.driver_status;
  const row = (k: string, v: any) => (v ? <View key={k} style={{ flexDirection: "row", justifyContent: "space-between", gap: space.md }}><T size={13} color={colors.muted}>{k}</T><T size={13} weight="700" style={{ flexShrink: 1 }}>{String(v)}</T></View> : null);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Driver review" />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl, width: "100%", maxWidth: 900, alignSelf: "center" }}>
        <Card style={{ gap: space.sm }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm }}>
            <T testID="admin-driver-name" size={18} weight="800" style={{ flex: 1 }}>{u.name}</T>
            <Badge testID="admin-driver-status" label={t(`verify.status.${status}`)} tone={statusTone(status)} />
          </View>
          {row("Email", u.email)}{row("Phone", u.phone)}{row("Driver ID", u.user_id)}{row("Legal name", doc.legal_name)}{row("Vehicle", doc.vehicle_name)}
          {row("Licence no.", doc.licence_no)}{row("Licence expiry", doc.licence_expiry)}{row("RC no.", doc.rc_no)}{row("Trips published", d.trips)}
          {row("Submitted", doc.submitted_at && new Date(doc.submitted_at + "Z").toLocaleString())}
          {u.suspended ? <T color={colors.error} weight="700">Account suspended</T> : null}
          {d.missing.length ? <T size={12} color={colors.error}>Missing: {d.missing.map((k: string) => d.labels[k]).join(", ")}</T> : null}
        </Card>

        <Section title={`Documents (${d.files.length})`}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
            {d.files.length === 0 ? <T color={colors.muted}>No documents uploaded</T> : null}
            {d.files.map((f: any) => {
              const pdf = f.content_type === "application/pdf";
              return (
                <Pressable key={f.file_id} testID={`admin-doc-${f.kind}-${f.file_id}`} onPress={() => (pdf ? WebBrowser.openBrowserAsync(adminFileUrl(f.file_id)) : setPreview(adminFileUrl(f.file_id)))}
                  style={{ width: 150, gap: 4 }}>
                  <View style={{ width: 150, height: 110, borderRadius: radius.md, overflow: "hidden", backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
                    {pdf ? <Ionicons name="document-text" size={40} color={colors.brandPrimary} /> : <Image source={{ uri: adminFileUrl(f.file_id) }} style={{ width: "100%", height: "100%" }} contentFit="cover" />}
                  </View>
                  <T size={12} weight="700">{d.labels[f.kind] ?? f.kind}</T>
                  <T size={11} color={colors.muted}>{pdf ? "PDF" : "Photo"} · {Math.round(f.size / 1024)} KB</T>
                </Pressable>
              );
            })}
          </View>
        </Section>

        <Card style={{ gap: space.sm }}>
          <T weight="800">Verification decision</T>
          <Field testID="admin-driver-note" label="Reason / note to driver (required for reject or resubmission)" value={note} onChangeText={setNote} multiline />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            <Btn testID="admin-driver-approve" icon="checkmark-circle" label="Approve" loading={busy === "approved"} disabled={!["under_review", "approved"].includes(status) || status === "approved"} onPress={() => act("approved", `/admin/drivers/${id}/review`, { decision: "approved", note })} />
            <Btn testID="admin-driver-resubmit" variant="outline" icon="refresh" label="Request resubmission" loading={busy === "resubmit"} disabled={!["under_review", "approved"].includes(status)} onPress={() => act("resubmit", `/admin/drivers/${id}/review`, { decision: "resubmit", note })} />
            <Btn testID="admin-driver-reject" variant="danger" icon="close-circle" label="Reject" loading={busy === "rejected"} disabled={!["under_review", "approved"].includes(status)} onPress={() => act("rejected", `/admin/drivers/${id}/review`, { decision: "rejected", note })} />
          </View>
          <Btn testID="admin-driver-suspend" variant={u.suspended ? "primary" : "ghost"} icon={u.suspended ? "lock-open-outline" : "ban-outline"} label={u.suspended ? "Reactivate account" : "Suspend account"} loading={busy === "susp"}
            onPress={() => act("susp", `/admin/users/${id}/suspend`, { suspended: !u.suspended })} />
        </Card>

        <Section title="Verification history">
          {d.history.length === 0 ? <T color={colors.muted}>No history yet</T> : null}
          {d.history.map((h: any) => (
            <View key={h.event_id} testID={`admin-history-${h.event_id}`} style={{ paddingVertical: space.sm, borderBottomWidth: 1, borderBottomColor: colors.border }}>
              <T size={13} weight="700">{h.action} · by {h.by_name}</T>
              {h.note ? <T size={12}>{h.note}</T> : null}
              <T size={11} color={colors.muted}>{new Date(h.at + "Z").toLocaleString()}</T>
            </View>
          ))}
        </Section>
      </ScrollView>
      <Modal visible={!!preview} transparent animationType="fade" onRequestClose={() => setPreview(null)}>
        <Pressable testID="admin-doc-preview-close" style={{ flex: 1, backgroundColor: colors.scrim, alignItems: "center", justifyContent: "center", padding: space.lg }} onPress={() => setPreview(null)}>
          {preview ? <Image source={{ uri: preview }} style={{ width: "100%", height: "80%" }} contentFit="contain" /> : null}
        </Pressable>
      </Modal>
    </View>
  );
}
