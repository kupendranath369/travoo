import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useState } from "react";
import { FlatList, Modal, Pressable, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Btn, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const INDIAN_LANGUAGES = [
  "Kannada", "English", "Hindi", "Telugu", "Tamil", "Malayalam", "Marathi",
  "Bengali", "Gujarati", "Punjabi", "Odia", "Assamese", "Urdu", "Konkani",
  "Sanskrit", "Nepali", "Manipuri", "Bodo", "Dogri", "Maithili", "Santali",
];

interface LanguagePickerProps {
  value: string[];
  onChange: (langs: string[]) => void;
  testPrefix?: string;
}

export function LanguagePicker({ value, onChange, testPrefix = "lang" }: LanguagePickerProps) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [visible, setVisible] = useState(false);
  const [search, setSearch] = useState("");
  const [tempSelected, setTempSelected] = useState<string[]>(value);

  const filteredLanguages = INDIAN_LANGUAGES.filter((lang) =>
    lang.toLowerCase().includes(search.toLowerCase())
  );

  const toggleLanguage = (lang: string) => {
    setTempSelected((prev) =>
      prev.includes(lang) ? prev.filter((l) => l !== lang) : [...prev, lang]
    );
  };

  const handleSave = () => {
    onChange(tempSelected);
    setVisible(false);
    setSearch("");
  };

  const handleCancel = () => {
    setTempSelected(value);
    setVisible(false);
    setSearch("");
  };

  const handleClear = () => {
    setTempSelected([]);
  };

  return (
    <>
      <Pressable
        testID={`${testPrefix}-trigger`}
        onPress={() => {
          setTempSelected(value);
          setVisible(true);
        }}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: space.sm,
          padding: space.md,
          borderWidth: 1,
          borderColor: colors.border,
          borderRadius: radius.md,
          backgroundColor: colors.surface,
        }}
      >
        <Ionicons name="language-outline" size={20} color={colors.brandPrimary} />
        <View style={{ flex: 1 }}>
          <T size={12} color={colors.muted}>Languages Spoken</T>
          <T size={14} weight="600" numberOfLines={1}>
            {value.length > 0 ? value.join(", ") : "Select languages"}
          </T>
        </View>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>

      <Modal visible={visible} animationType="slide" onRequestClose={handleCancel}>
        <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
          {/* Header */}
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            padding: space.md,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
          }}>
            <Pressable testID={`${testPrefix}-close`} onPress={handleCancel} hitSlop={8} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="close" size={24} color={colors.onSurface} />
            </Pressable>
            <T size={18} weight="800" style={{ flex: 1, textAlign: "center" }}>Select Languages</T>
            <View style={{ width: 44 }} />
          </View>

          {/* Search */}
          <View style={{
            margin: space.lg,
            marginBottom: space.sm,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.md,
            flexDirection: "row",
            alignItems: "center",
            paddingHorizontal: space.md,
            height: 48,
          }}>
            <Ionicons name="search" size={18} color={colors.muted} />
            <TextInput
              testID={`${testPrefix}-search`}
              value={search}
              onChangeText={setSearch}
              placeholder="Search languages..."
              placeholderTextColor={colors.muted}
              style={{ flex: 1, marginLeft: space.sm, color: colors.onSurface, fontSize: 16 }}
            />
            {search ? (
              <Pressable onPress={() => setSearch("")} hitSlop={8}>
                <Ionicons name="close-circle" size={18} color={colors.muted} />
              </Pressable>
            ) : null}
          </View>

          {/* Selected Languages */}
          {tempSelected.length > 0 ? (
            <View style={{
              marginHorizontal: space.lg,
              marginBottom: space.sm,
              flexDirection: "row",
              flexWrap: "wrap",
              gap: space.sm,
            }}>
              {tempSelected.map((lang) => (
                <Pressable
                  key={lang}
                  testID={`${testPrefix}-selected-${lang}`}
                  onPress={() => toggleLanguage(lang)}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: space.xs,
                    paddingHorizontal: space.sm,
                    paddingVertical: space.xs,
                    backgroundColor: colors.brandPrimary,
                    borderRadius: radius.pill,
                  }}
                >
                  <T size={12} weight="600" color={colors.onBrandPrimary}>{lang}</T>
                  <Ionicons name="close" size={14} color={colors.onBrandPrimary} />
                </Pressable>
              ))}
            </View>
          ) : null}

          {/* Clear All */}
          {tempSelected.length > 0 ? (
            <Pressable
              testID={`${testPrefix}-clear-all`}
              onPress={handleClear}
              style={{
                marginHorizontal: space.lg,
                marginBottom: space.sm,
                alignSelf: "flex-end",
              }}
            >
              <T size={12} weight="700" color={colors.error}>Clear All</T>
            </Pressable>
          ) : null}

          {/* Language List */}
          <FlatList
            data={filteredLanguages}
            keyExtractor={(item) => item}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: insets.bottom + space.xl }}
            renderItem={({ item }) => {
              const isSelected = tempSelected.includes(item);
              return (
                <Pressable
                  testID={`${testPrefix}-item-${item}`}
                  onPress={() => toggleLanguage(item)}
                  style={({ pressed }) => ({
                    flexDirection: "row",
                    alignItems: "center",
                    gap: space.sm,
                    paddingVertical: space.md,
                    paddingHorizontal: space.sm,
                    borderBottomWidth: 1,
                    borderBottomColor: colors.divider,
                    backgroundColor: pressed ? colors.surfaceTertiary : "transparent",
                  })}
                >
                  <View style={{
                    width: 24,
                    height: 24,
                    borderRadius: 12,
                    borderWidth: 2,
                    borderColor: isSelected ? colors.brandPrimary : colors.border,
                    backgroundColor: isSelected ? colors.brandPrimary : "transparent",
                    alignItems: "center",
                    justifyContent: "center",
                  }}>
                    {isSelected ? <Ionicons name="checkmark" size={14} color={colors.onBrandPrimary} /> : null}
                  </View>
                  <T weight="600" style={{ flex: 1 }}>{item}</T>
                </Pressable>
              );
            }}
            ListEmptyComponent={
              <T color={colors.muted} style={{ paddingVertical: space.lg, textAlign: "center" }}>
                No languages found
              </T>
            }
          />

          {/* Footer Buttons */}
          <View style={{
            padding: space.lg,
            paddingBottom: insets.bottom + space.lg,
            borderTopWidth: 1,
            borderTopColor: colors.border,
            backgroundColor: colors.surfaceSecondary,
            gap: space.sm,
          }}>
            <Btn
              testID={`${testPrefix}-save`}
              label={`Save (${tempSelected.length})`}
              onPress={handleSave}
              icon="checkmark"
            />
            <Btn
              testID={`${testPrefix}-cancel`}
              variant="ghost"
              label="Cancel"
              onPress={handleCancel}
            />
          </View>
        </View>
      </Modal>
    </>
  );
}
