import { useLocalSearchParams, useRouter } from "expo-router";
import React from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Badge, Card, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { LEGAL_DOCS } from "@/src/legal";
import { useTheme } from "@/src/theme";

export default function LegalScreen() {
  const { doc } = useLocalSearchParams<{ doc?: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const d = doc ? LEGAL_DOCS[doc] : null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={d ? t(`legal.${doc}`) : t("profile.legal")} />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Badge label={t("legal.review_note")} tone="warning" />
        {d ? (
          d.map(([h, body], i) => (
            <View key={i} style={{ gap: 4 }}>
              <T weight="800">{h}</T>
              <T size={13} color={colors.onSurfaceSecondary} style={{ fontFamily: "PJS-Regular" }}>{body}</T>
            </View>
          ))
        ) : (
          Object.keys(LEGAL_DOCS).map((k) => (
            <Card key={k} testID={`legal-doc-${k}`} onPress={() => router.push(`/legal?doc=${k}`)}>
              <T weight="700">{t(`legal.${k}`)}</T>
            </Card>
          ))
        )}
      </ScrollView>
    </View>
  );
}
