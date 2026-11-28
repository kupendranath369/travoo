import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import Ionicons from "@react-native-vector-icons/ionicons";
import { Pressable, Text, View } from "react-native";
import Animated, { Easing, FadeIn, FadeInDown, FadeOut, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";

const BG = "#001A33";

/** Opening screen: sunset highway photo with the Travoo logo. */
export function Splash({ onStart }: { onStart?: () => void }) {
  const zoom = useSharedValue(1.08);
  const glow = useSharedValue(0.4);
  useEffect(() => {
    zoom.value = withTiming(1, { duration: 2600, easing: Easing.out(Easing.quad) });
    glow.value = withRepeat(withSequence(withTiming(1, { duration: 700 }), withTiming(0.4, { duration: 700 })), -1);
  }, [zoom, glow]);
  const bg = useAnimatedStyle(() => ({ transform: [{ scale: zoom.value }] }));
  const arrow = useAnimatedStyle(() => ({ transform: [{ translateX: (glow.value - 0.4) * 8 }] }));
  return (
    <Animated.View entering={FadeIn.duration(400)} exiting={FadeOut.duration(500)} testID="splash-screen" style={{ flex: 1, backgroundColor: BG, overflow: "hidden" }}>
      <Animated.View style={[{ position: "absolute", width: "100%", height: "100%" }, bg]}>
        <Image testID="splash-background" source={require("@/assets/images/splash-bg.jpg")} style={{ width: "100%", height: "100%" }} contentFit="cover" contentPosition="bottom" />
      </Animated.View>
      <LinearGradient colors={[BG, "rgba(0,26,51,0.6)", "rgba(0,26,51,0)"]} locations={[0, 0.3, 0.55]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <Animated.View entering={FadeInDown.delay(250).duration(700)} style={{ alignItems: "center", paddingTop: "28%", paddingHorizontal: 32, gap: 18 }}>
        <Image testID="splash-logo" source={require("@/assets/images/travoo-wordmark-white.png")} style={{ width: "78%", maxWidth: 340, aspectRatio: 1598 / 417 }} contentFit="contain" accessibilityLabel="Travoo" />
        <Text testID="splash-tagline" style={{ fontFamily: "PJS-SemiBold", fontSize: 22, color: "#FFFFFF", letterSpacing: 1 }}>Enjoy Your Ride</Text>
      </Animated.View>
      <Animated.View entering={FadeInDown.delay(600).duration(600)} style={{ position: "absolute", bottom: 56, left: 24, right: 24 }}>
        <Pressable testID="splash-get-started" onPress={onStart} accessibilityRole="button"
          style={({ pressed }) => ({ transform: [{ scale: pressed ? 0.97 : 1 }], opacity: onStart ? 1 : 0.85 })}>
          <LinearGradient colors={["#E2B651", "#C5A059", "#A9823A"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={{ height: 58, borderRadius: 29, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 }}>
            <Text style={{ fontFamily: "PJS-ExtraBold", fontSize: 20, color: "#FFFFFF" }}>Get Started</Text>
            <Animated.View style={arrow}><Ionicons name="arrow-forward" size={22} color="#FFFFFF" /></Animated.View>
          </LinearGradient>
        </Pressable>
      </Animated.View>
    </Animated.View>
  );
}
