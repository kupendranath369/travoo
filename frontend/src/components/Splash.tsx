import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import { Text, View } from "react-native";
import Animated, { Easing, FadeIn, FadeInDown, FadeOut, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";

const BG = "#001A33";

/** Opening screen: sunset highway photo with the Travoo logo. */
export function Splash() {
  const zoom = useSharedValue(1.08);
  const glow = useSharedValue(0.4);
  useEffect(() => {
    zoom.value = withTiming(1, { duration: 2600, easing: Easing.out(Easing.quad) });
    glow.value = withRepeat(withSequence(withTiming(1, { duration: 700 }), withTiming(0.4, { duration: 700 })), -1);
  }, [zoom, glow]);
  const bg = useAnimatedStyle(() => ({ transform: [{ scale: zoom.value }] }));
  const dot = useAnimatedStyle(() => ({ opacity: glow.value }));
  return (
    <Animated.View entering={FadeIn.duration(400)} exiting={FadeOut.duration(500)} testID="splash-screen" style={{ flex: 1, backgroundColor: BG, overflow: "hidden" }}>
      <Animated.View style={[{ position: "absolute", width: "100%", height: "100%" }, bg]}>
        <Image testID="splash-background" source={require("@/assets/images/splash-bg.jpg")} style={{ width: "100%", height: "100%" }} contentFit="cover" contentPosition="bottom" />
      </Animated.View>
      <LinearGradient colors={[BG, "rgba(0,26,51,0.6)", "rgba(0,26,51,0)"]} locations={[0, 0.3, 0.55]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <Animated.View entering={FadeInDown.delay(250).duration(700)} style={{ alignItems: "center", paddingTop: "28%", paddingHorizontal: 32, gap: 18 }}>
        <Image testID="splash-logo" source={require("@/assets/images/travoo-logo-white.png")} style={{ width: "86%", maxWidth: 360, aspectRatio: 1867 / 295 }} contentFit="contain" accessibilityLabel="Travoo" />
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          {["Travel", "Share", "Drive"].map((w, i) => (
            <React.Fragment key={w}>
              {i ? <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: "#F5A623" }} /> : null}
              <Text style={{ fontFamily: "PJS-SemiBold", fontSize: 17, color: "#FFFFFF", letterSpacing: 0.5 }}>{w}</Text>
            </React.Fragment>
          ))}
        </View>
      </Animated.View>
      <View style={{ position: "absolute", bottom: 48, left: 0, right: 0, flexDirection: "row", justifyContent: "center", gap: 8 }}>
        {[0, 1, 2].map((i) => <Animated.View key={i} style={[{ width: 8, height: 8, borderRadius: 4, backgroundColor: "#FFFFFF" }, i === 1 ? dot : { opacity: 0.5 }]} />)}
      </View>
    </Animated.View>
  );
}
