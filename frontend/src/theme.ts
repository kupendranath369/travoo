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
  surface: "#FBF7EF", // warm cream canvas
  onSurface: "#17263D", // deep navy text and icons
  surfaceSecondary: "#FFFFFF", // cards, sheets, list rows
  onSurfaceSecondary: "#17263D", // text and icons on cards, sheets, rows
  surfaceTertiary: "#F5EFE3", // input backgrounds, chips, deepest nesting
  onSurfaceTertiary: "#17263D", // text on inputs and chips; also muted text
  surfaceInverse: "#17263D", // tooltips, snackbars, anything popping against the theme
  onSurfaceInverse: "#FFFFFF", // text and icons on the inverse surface
  muted: "#6B778C", // subdued text on surface: captions, timestamps, placeholders

  // ---------------------------------------------------------------------------
  // Brand: the identity color and the fills built from it.
  // Navy and warm gold identity from the provided Travoo reference.
  // ---------------------------------------------------------------------------
  brand: "#17263D", // deep navy brand anchor
  onBrand: "#FFFFFF", // text and icons placed directly on brand
  brandPrimary: "#C99422", // warm gold primary CTA and selected states
  onBrandPrimary: "#17263D", // navy text and icons on gold
  brandSecondary: "#A87916", // deeper gold for secondary accents
  onBrandSecondary: "#FFFFFF", // text and icons on brandSecondary
  brandTertiary: "#E4B84E", // lighter gold for chips, tags, and badges
  onBrandTertiary: "#17263D", // navy text on gold

  // ---------------------------------------------------------------------------
  // Status: semantic only, never decorative. Fill for badges, banners and
  // toasts; the `on` key is text on that fill. The plain key is also safe as
  // text on `surface`.
  // ---------------------------------------------------------------------------
  success: "#28795A",
  onSuccess: "#FFFFFF",
  warning: "#F5CD47",
  onWarning: "#172B4D",
  error: "#CA3521",
  onError: "#FFFFFF",
  info: "#315C87",
  onInfo: "#FFFFFF",

  // ---------------------------------------------------------------------------
  // Lines
  // ---------------------------------------------------------------------------
  border: "#E7DFD1", // warm hairline outline
  borderStrong: "#B9A98C", // focus rings and selected outlines
  divider: "#E7DFD1", // subtle list separators
  brandSoft: "#F7EBCB", // pale gold fills
  accentSoft: "#F3E9D9", // pale warm fills
  successSoft: "#E5F1EA",
  scrim: "rgba(23,38,61,0.58)",
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
