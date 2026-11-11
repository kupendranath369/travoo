import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { api } from "@/src/api";
import { Btn, Field, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const FLAGS: Record<string, string> = { "91": "IN", "971": "AE", "1": "US/CA", "44": "UK", "65": "SG", "977": "NP", "880": "BD", "94": "LK", "61": "AU", "966": "SA", "974": "QA", "968": "OM", "973": "BH", "965": "KW" };

/** Mobile number + OTP (sent by SMS from the server). `sendPath`/`verifyPath` switch between sign-in and linking a number. */
export function PhoneOtp({ sendPath = "/auth/otp/send", verifyPath = "/auth/otp/verify", onVerified, submitLabel = "Verify & continue", testPrefix = "otp" }: {
  sendPath?: string; verifyPath?: string; onVerified: (r: any) => Promise<void> | void; submitLabel?: string; testPrefix?: string;
}) {
  const { colors } = useTheme();
  const [codes, setCodes] = useState<string[]>(["91"]);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [cc, setCc] = useState("91");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { api("/auth/otp/status").then((r) => { setCodes(r.countries); setEnabled(r.enabled); }).catch(() => setEnabled(false)); }, []);
  useEffect(() => {
    if (!wait) return;
    const h = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(h);
  }, [wait]);

  const valid = cc === "91" ? /^[6-9]\d{9}$/.test(phone) : /^\d{6,12}$/.test(phone);
  const send = async (resend = false) => {
    setErr("");
    if (!valid) return setErr(cc === "91" ? "Enter a valid 10-digit mobile number" : "Enter a valid mobile number");
    setBusy("send");
    try {
      const r = await api(sendPath, { body: { country_code: cc, phone, resend } });
      setSentTo(r.phone);
      setWait(30);
    } catch (e: any) { setErr(e.message); }
    setBusy("");
  };
  const verify = async () => {
    setErr("");
    if (!/^\d{4,8}$/.test(otp)) return setErr("Enter the 6-digit OTP");
    setBusy("verify");
    try { await onVerified(await api(verifyPath, { body: { country_code: cc, phone, otp } })); } catch (e: any) { setErr(e.message); }
    setBusy("");
  };

  return (
    <View style={{ gap: space.md }}>
      {enabled === false ? (
        <View testID={`${testPrefix}-disabled`} style={{ backgroundColor: colors.accentSoft, borderRadius: radius.md, padding: space.md }}>
          <T size={13} weight="600" color={colors.brandTertiary}>{testPrefix === "auth-otp" ? "Mobile OTP sign-in is not switched on yet. Existing users can sign in with email below." : "Mobile OTP verification is not switched on yet. You can add your number with Edit profile for now."}</T>
        </View>
      ) : null}
      {!sentTo ? (
        <>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {codes.map((c) => (
              <Pressable key={c} testID={`${testPrefix}-cc-${c}`} onPress={() => setCc(c)} style={{ flexShrink: 0, height: 36, paddingHorizontal: space.md, borderRadius: radius.pill, justifyContent: "center", borderWidth: 1, borderColor: cc === c ? colors.brandPrimary : colors.border, backgroundColor: cc === c ? colors.brandSoft : colors.surfaceSecondary }}>
                <T size={13} weight="700" color={cc === c ? colors.brandPrimary : colors.onSurface}>+{c} {FLAGS[c]}</T>
              </Pressable>
            ))}
          </ScrollView>
          <Field testID={`${testPrefix}-phone-input`} label={`Mobile number (+${cc})`} value={phone} onChangeText={(v) => setPhone(v.replace(/\D/g, "").slice(0, 12))} keyboardType="phone-pad" maxLength={12} placeholder={cc === "91" ? "98765 43210" : ""} />
          {err ? <T testID={`${testPrefix}-error`} color={colors.error} weight="600">{err}</T> : null}
          <Btn testID={`${testPrefix}-send-button`} icon="chatbubble-ellipses-outline" label="Send OTP" loading={busy === "send"} disabled={!valid || enabled === false} onPress={() => send(false)} />
        </>
      ) : (
        <>
          <T testID={`${testPrefix}-sent-to`} size={13} color={colors.muted}>We sent a 6-digit code by SMS to {sentTo}. It is valid for 10 minutes.</T>
          <Field testID={`${testPrefix}-code-input`} label="OTP" value={otp} onChangeText={(v) => setOtp(v.replace(/\D/g, "").slice(0, 8))} keyboardType="number-pad" maxLength={8} textContentType="oneTimeCode" autoComplete="sms-otp" />
          {err ? <T testID={`${testPrefix}-error`} color={colors.error} weight="600">{err}</T> : null}
          <Btn testID={`${testPrefix}-verify-button`} label={submitLabel} loading={busy === "verify"} disabled={otp.length < 4} onPress={verify} />
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Pressable testID={`${testPrefix}-change-number`} hitSlop={8} onPress={() => { setSentTo(""); setOtp(""); setErr(""); }}><T weight="700" color={colors.brandPrimary}>Change number</T></Pressable>
            <Pressable testID={`${testPrefix}-resend`} hitSlop={8} disabled={wait > 0 || !!busy} onPress={() => send(true)}><T weight="700" color={wait ? colors.muted : colors.brandPrimary}>{wait ? `Resend in ${wait}s` : "Resend OTP"}</T></Pressable>
          </View>
        </>
      )}
    </View>
  );
}
