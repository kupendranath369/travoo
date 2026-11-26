// Design tokens for this app. Light theme only.Always modify the colors and theme to Dark, Light or Dark and Light according to the design guidelines.
//
// The keys match the "color" block of /app/design_guidelines.json. Fill the
// values from that file (or from the user's brand colors). Keep every key; do
// not add a second theme or colors file; do not write color literals in
// components.
//
// How the names work: a plain key is a background, and its `on` partner is the
// text or icon color that sits on top of it. Always use them as a pair.
//   <View style={{ backgroundColor: colors.brandPrimary }}>
//     <Text style={{ color: colors.onBrandPrimary }}>Continue</Text>
//   </View>
//
// Styling a screen or component: build the sheet with makeStyles so colors
// and layout live together and follow the active scheme:
//   const useStyles = makeStyles((colors) => ({
//     card: { backgroundColor: colors.surfaceSecondary, padding: 16 },
//     title: { color: colors.onSurfaceSecondary, fontSize: 16 },
//   }));
//   function Screen() {
//     const styles = useStyles();
//     return <View style={styles.card}><Text style={styles.title}>Hi</Text></View>;
//   }
// For color props that are not styles (icon color, placeholderTextColor,
// ActivityIndicator) read useTheme().colors inside the component.
// Never call StyleSheet.create with color values at module level; it cannot
// follow the scheme.
//
// To support dark mode later: add `dark` to `themes` with every key filled.
// Nothing else changes; the device setting takes over automatically.
// Feel free to add as many new colors as you need to support the design guidelines.

import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme, type ImageStyle, type TextStyle, type ViewStyle } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  // ---------------------------------------------------------------------------
  // Surfaces: backgrounds, from the screen down to small fills.
  // Each `on` key is the text and icon color for that background.
  // ---------------------------------------------------------------------------
  surface: "#F8F6F1", // Ivory White app background
  onSurface: "#14243A", // Midnight Navy
  surfaceSecondary: "#FFFFFF", // cards, sheets, list rows
  onSurfaceSecondary: "#14243A", // text and icons on cards, sheets, rows
  surfaceTertiary: "#F8F6F1", // input backgrounds and deepest nesting
  onSurfaceTertiary: "#14243A", // text on inputs and chips
  surfaceInverse: "#14243A", // tooltips, snackbars, anything popping against the theme
  onSurfaceInverse: "#FFFFFF", // text and icons on the inverse surface
  muted: "#64748B", // Slate Gray secondary text

  // ---------------------------------------------------------------------------
  // Brand: the identity color and the fills built from it.
  // Navy and warm gold identity from the provided Travoo reference.
  // ---------------------------------------------------------------------------
  brand: "#14243A", // Midnight Navy brand identity
  onBrand: "#FFFFFF", // text and icons placed directly on brand
  brandPrimary: "#14243A", // Midnight Navy primary buttons
  onBrandPrimary: "#FFFFFF", // white text on navy buttons
  brandSecondary: "#C5A059", // Champagne Gold premium accent
  onBrandSecondary: "#14243A", // navy text on gold
  brandTertiary: "#C5A059", // Champagne Gold selected icons and badges
  onBrandTertiary: "#14243A", // navy text on gold

  // ---------------------------------------------------------------------------
  // Status: semantic only, never decorative. Fill for badges, banners and
  // toasts; the `on` key is text on that fill. The plain key is also safe as
  // text on `surface`.
  // ---------------------------------------------------------------------------
  success: "#28795A",
  onSuccess: "#FFFFFF",
  warning: "#F5CD47",
  onWarning: "#14243A",
  error: "#CA3521",
  onError: "#FFFFFF",
  info: "#315C87",
  onInfo: "#FFFFFF",

  // ---------------------------------------------------------------------------
  // Lines
  // ---------------------------------------------------------------------------
  border: "rgba(100,116,139,0.2)", // softened Slate Gray outline
  borderStrong: "#C5A059", // Champagne Gold selected outline
  divider: "rgba(100,116,139,0.16)", // subtle Slate Gray separators
  brandSoft: "#F8F6F1", // Ivory White subtle fill
  accentSoft: "#F8F6F1", // Ivory White accent fill
  successSoft: "#E5F1EA",
  scrim: "rgba(20,36,58,0.58)",
};

export type ThemeColors = typeof light;

export const defaultScheme = "light" satisfies ColorScheme;

export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

// In-app theme toggle, only after `dark` exists in `themes`. Call
// setColorScheme("dark"), setColorScheme("light"), or setColorScheme(null) to
// follow the device. Every useTheme() consumer re-renders. Persisting the
// choice and re-applying it on launch is the toggle's job.
export function setColorScheme(scheme: ColorScheme | null) {
  // RN 0.86 re-reads the device scheme only for the literal "unspecified";
  // null would pin useColorScheme() to null and the app to light.
  Appearance.setColorScheme?.(scheme ?? "unspecified");
}

// Keep native surfaces (alerts, pickers, navigation chrome) on the schemes this
// app ships: light only forces light; once `dark` exists the device decides.
// Optional call because react-native-web does not implement it.
setColorScheme?.(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = (system === "light" || system === "dark") && themes[system] ? system : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

// Themed StyleSheet: returns a hook that builds the sheet from the active
// scheme's colors and memoizes it until the scheme changes.
type NamedStyles = Record<string, ViewStyle | TextStyle | ImageStyle>;

export function makeStyles<T extends NamedStyles>(factory: (colors: ThemeColors) => T): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors) as any) as T, [colors]);
  };
}
