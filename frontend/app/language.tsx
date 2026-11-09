import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { LogoFull } from "@/src/components/Logo";
import { Badge, Btn, T, radius, space } from "@/src/components/ui";
import { LANGUAGES, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function LanguageScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { lang, setLang, t } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const [sel, setSel] = useState(lang);

  const done = async () => {
    await setLang(sel);
    if (from === "profile" && router.canGoBack()) router.back();
    else router.replace(user ? "/" : "/auth");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <FlatList
        testID="language-list"
        data={LANGUAGES}
        numColumns={2}
        keyExtractor={(l) => l.code}
        columnWrapperStyle={{ gap: space.md }}
        contentContainerStyle={{ padding: space.lg, paddingTop: insets.top + space.lg, gap: space.md, paddingBottom: 120 + insets.bottom }}
        ListHeaderComponent={
          <View style={{ gap: space.md, marginBottom: space.md }}>
            <LogoFull width={150} />
            <T size={24} weight="800">{t("lang.title")}</T>
            <T color={colors.muted}>{t("lang.sub")}</T>
          </View>
        }
        renderItem={({ item }) => {
          const active = sel === item.code;
          const planned = item.status === "planned";
          return (
            <Pressable
              testID={`language-option-${item.code}`}
              disabled={planned}
              onPress={() => setSel(item.code)}
              style={{ flex: 1, minHeight: 84, borderRadius: radius.lg, padding: space.md, borderWidth: active ? 2 : 1, borderColor: active ? colors.brandPrimary : colors.border, backgroundColor: active ? colors.brandSoft : colors.surfaceSecondary, opacity: planned ? 0.5 : 1, gap: 2 }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <Text style={{ fontSize: 18, fontWeight: "700", color: colors.onSurface }}>{item.native}</Text>
                {active ? <Ionicons name="checkmark-circle" size={20} color={colors.brandPrimary} /> : null}
              </View>
              <T size={12} color={colors.muted}>{item.english}</T>
              {planned ? <Badge label="Coming soon" tone="muted" /> : null}
            </Pressable>
          );
        }}
      />
      <View style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: space.lg, paddingBottom: insets.bottom + space.lg, backgroundColor: colors.surfaceSecondary, borderTopWidth: 1, borderTopColor: colors.border }}>
        <Btn testID="language-continue-button" label={t("lang.continue")} onPress={done} />
      </View>
    </View>
  );
}
