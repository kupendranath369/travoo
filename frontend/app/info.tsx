import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams } from "expo-router";
import React from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { LogoFull } from "@/src/components/Logo";
import { Badge, Card, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function InfoScreen() {
  const { s = "about" } = useLocalSearchParams<{ s?: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const titles: Record<string, string> = { about: t("v2.about"), how: t("home.how"), why: t("home.why"), testimonials: t("home.testimonials"), faq: t("home.faq"), safety: t("safety.title"), verification: t("v2.driver_info") };
  const row = (icon: any, title: string, body: string, key: string) => (
    <Card key={key} style={{ flexDirection: "row", gap: space.md }}>
      <Ionicons name={icon} size={22} color={colors.brandPrimary} />
      <View style={{ flex: 1, gap: 2 }}>
        <T weight="800">{title}</T>
        <T size={13} color={colors.muted}>{body}</T>
      </View>
    </Card>
  );
  const content: Record<string, React.ReactNode> = {
    about: (<><View style={{ alignItems: "center" }}><LogoFull width={180} /></View><T>{t("v2.about_body")}</T><T weight="700" color={colors.brandPrimary}>{t("app.motto")}</T></>),
    how: [1, 2, 3, 4].map((n) => row(["search", "ticket", "car-sport", "cash"][n - 1], `${n}. ${t(`how.${n}.t`)}`, t(`how.${n}.d`), String(n))),
    why: ["verified", "afford", "safety", "lang"].map((k, i) => row(["shield-checkmark", "wallet", "alert-circle", "language"][i], t(`why.${k}.t`), t(`why.${k}.d`), k)),
    testimonials: (<><Badge label={t("home.sample")} tone="muted" />{[["Rohit, Pune", 1], ["Lakshmi, Madurai", 2]].map(([n, i]) => row("chatbox-ellipses", String(n), `“${t(`testi.${i}`)}”`, String(i)))}</>),
    faq: [1, 2, 3, 4].map((i) => row("help-circle", t(`faq.${i}.q`), t(`faq.${i}.a`), String(i))),
    safety: (<>{[1, 2, 3, 4].map((i) => row("shield-checkmark-outline", t("safety.title"), t(`safety.${i}`), String(i)))}{row("warning", t("sos.title"), t("sos.body"), "sos")}</>),
    verification: row("id-card", t("v2.driver_info"), t("v2.driver_info_body"), "v"),
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={titles[s] ?? titles.about} />
      <ScrollView testID={`info-${s}`} contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>{content[s] ?? content.about}</ScrollView>
    </View>
  );
}
