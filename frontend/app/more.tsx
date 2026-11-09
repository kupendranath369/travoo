import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React from "react";
import { Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Card, Header, IconName, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

type Item = [IconName, string, string];

export default function MoreScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const { logout, user } = useAuth();
  const groups: [string, Item[]][] = [
    [t("v2.info"), [["information-circle-outline", t("v2.about"), "/info?s=about"], ["git-network-outline", t("home.how"), "/info?s=how"], ["star-outline", t("home.why"), "/info?s=why"], ["chatbox-ellipses-outline", t("home.testimonials"), "/info?s=testimonials"], ["help-circle-outline", t("home.faq"), "/info?s=faq"]]],
    [t("v2.safety_support"), [["shield-checkmark-outline", t("safety.title"), "/info?s=safety"], ["id-card-outline", t("v2.driver_info"), "/info?s=verification"], ["flag-outline", t("v2.reports"), "/support?type=report_user"], ["help-buoy-outline", t("profile.support"), "/support"]]],
    [t("v2.legal"), [["document-text-outline", t("legal.terms"), "/legal?doc=terms"], ["lock-closed-outline", t("legal.privacy"), "/legal?doc=privacy"], ["car-outline", t("legal.driver"), "/legal?doc=driver"], ["person-outline", t("legal.passenger"), "/legal?doc=passenger"], ["close-circle-outline", t("legal.cancellation"), "/legal?doc=cancellation"], ["checkbox-outline", t("legal.compliance"), "/legal?doc=compliance"], ["megaphone-outline", t("support.grievance"), "/support?type=complaint"]]],
    [t("v2.account"), [["create-outline", t("profile.edit"), "/profile"], ["language-outline", t("profile.language"), "/language?from=profile"], ["ticket-outline", t("tab.bookings"), "/bookings"], ["chatbubbles-outline", t("v2.messages"), "/messages"], ["shield-outline", t("profile.verification"), "/driver"], ["briefcase-outline", t("v2.local_register"), "/hire/register"], ["key-outline", t("v2.hire"), "/hire"], ["wallet-outline", t("profile.earnings"), "/earnings"]]],
  ];
  
  // Add admin section if user is admin
  if (user?.role === "admin") {
    groups.unshift([t("admin.title"), [["shield-checkmark-outline", t("admin.title"), "/admin"]]]);
  }
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.more")} />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        {groups.map(([title, items]) => (
          <View key={title} style={{ gap: space.sm }}>
            <T size={13} weight="700" color={colors.muted}>{title.toUpperCase()}</T>
            <Card style={{ paddingVertical: space.xs }}>
              {items.map(([icon, label, href]) => (
                <Pressable key={href} testID={`more-${href.replace(/[^a-z]/gi, "-")}`} onPress={() => router.push(href as any)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 48 }}>
                  <Ionicons name={icon} size={20} color={colors.brandPrimary} />
                  <T weight="600" style={{ flex: 1 }}>{label}</T>
                  <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                </Pressable>
              ))}
            </Card>
          </View>
        ))}
        <Pressable testID="more-logout" onPress={logout} style={{ flexDirection: "row", gap: space.md, alignItems: "center", padding: space.md }}>
          <Ionicons name="log-out-outline" size={20} color={colors.error} />
          <T weight="700" color={colors.error}>{t("profile.logout")}</T>
        </Pressable>
      </ScrollView>
    </View>
  );
}
