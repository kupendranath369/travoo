import React, { useCallback, useEffect, useState } from "react";
import { View } from "react-native";

import { api } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Field, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

/** Driver-only card on their own upcoming trip: pay the platform by UPI, submit the reference, admin turns it on. */
export function FeatureCard({ tripId }: { tripId: string }) {
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const toast = useToast();
  const [cfg, setCfg] = useState<any>(null);
  const [req, setReq] = useState<any>(undefined);
  const [open, setOpen] = useState(false);
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    const [s, r] = await Promise.all([api("/settings"), api(`/trips/${tripId}/feature`).catch(() => null)]);
    setCfg(s);
    setReq(r);
  }, [tripId]);
  useEffect(() => { load(); }, [load]);

  if (!cfg || req === undefined) return null;
  const live = req?.status === "active" && new Date(req.expires_at) > new Date();
  const pending = req?.status === "pending";

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      await api(`/trips/${tripId}/feature`, { body: { payment_ref: ref.trim() } });
      toast(t("feat.sent"));
      setOpen(false);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card testID="feature-card" style={{ gap: space.md, borderColor: colors.brandTertiary }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.sm }}>
        <T size={16} weight="800" style={{ flex: 1 }}>{t("feat.title")}</T>
        {live ? <Badge testID="feature-status" icon="star" label={t("feat.live")} tone="success" /> : pending ? <Badge testID="feature-status" label={t("feat.pending")} tone="warning" /> : req?.status === "rejected" ? <Badge testID="feature-status" label={t("feat.rejected")} tone="error" /> : null}
      </View>
      {live ? (
        <T testID="feature-live-until" size={13} color={colors.muted}>{t("feat.live_until", { date: fmtDate(req.expires_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) })}</T>
      ) : pending ? (
        <T size={13} color={colors.muted}>{t("feat.pending_d", { ref: req.payment_ref })}</T>
      ) : (
        <>
          <T size={13} color={colors.muted}>{t("feat.pitch", { days: cfg.featured_days, price: inr(cfg.featured_price) })}</T>
          {req?.status === "rejected" && req.admin_note ? <T size={12} color={colors.error}>{req.admin_note}</T> : null}
          {!cfg.featured_upi_id ? (
            <T testID="feature-closed" size={13} weight="600" color={colors.muted}>{t("feat.closed")}</T>
          ) : open ? (
            <View style={{ gap: space.sm }}>
              <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, padding: space.md, gap: 4 }}>
                <T size={12} color={colors.muted}>{t("feat.pay_to")}</T>
                <T testID="feature-upi-id" weight="800" color={colors.brandTertiary} selectable>{cfg.featured_upi_id}</T>
                <T testID="feature-amount" weight="800">{inr(cfg.featured_price)}</T>
              </View>
              <Field testID="feature-payment-ref" label={t("feat.ref")} placeholder="e.g. 412345678901" value={ref} onChangeText={(x) => setRef(x.replace(/[^A-Za-z0-9-]/g, ""))} autoCapitalize="characters" />
              {err ? <T testID="feature-error" size={12} color={colors.error}>{err}</T> : null}
              <Btn testID="feature-submit-button" icon="send" label={t("feat.submit")} loading={busy} disabled={ref.trim().length < 6} onPress={submit} />
            </View>
          ) : (
            <Btn testID="feature-open-button" variant="outline" icon="star-outline" label={t("feat.cta", { price: inr(cfg.featured_price) })} onPress={() => setOpen(true)} />
          )}
        </>
      )}
    </Card>
  );
}
