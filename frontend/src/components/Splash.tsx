import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import { Text, useWindowDimensions, View } from "react-native";
import Animated, { Easing, FadeIn, FadeOut, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";

import { BrandPin, IMG, Wordmark } from "@/src/components/Brand";

const ROAD = 92;

/** Opening screen: blue sea coast with a car driving along the road. */
export function Splash() {
  const { width } = useWindowDimensions();
  const x = useSharedValue(-120);
  const bump = useSharedValue(0);
  const dash = useSharedValue(0);
  useEffect(() => {
    x.value = withRepeat(withTiming(width + 40, { duration: 2200, easing: Easing.inOut(Easing.quad) }), -1);
    bump.value = withRepeat(withSequence(withTiming(-3, { duration: 160 }), withTiming(0, { duration: 160 })), -1);
    dash.value = withRepeat(withTiming(-60, { duration: 500, easing: Easing.linear }), -1);
  }, [width, x, bump, dash]);
  const car = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }, { translateY: bump.value }] }));
  const lines = useAnimatedStyle(() => ({ transform: [{ translateX: dash.value }] }));
  return (
    <Animated.View entering={FadeIn.duration(500)} exiting={FadeOut.duration(500)} testID="splash-screen" style={{ flex: 1, backgroundColor: "#E8F4FD" }}>
      <LinearGradient colors={["#CFE7FB", "#EEF7FE"]} style={{ position: "absolute", width: "100%", height: "60%" }} />
      <View style={{ position: "absolute", left: 0, right: 0, bottom: ROAD, height: "42%" }}>
        <Image source={{ uri: IMG.header }} style={{ width: "100%", height: "100%" }} contentFit="cover" />
        <LinearGradient colors={["#EEF7FE", "rgba(238,247,254,0)"]} style={{ position: "absolute", left: 0, right: 0, top: 0, height: 70 }} />
      </View>
      <View style={{ alignItems: "center", paddingTop: "22%", gap: 10 }}>
        <BrandPin size={64} />
        <Wordmark size={56} />
        <Text style={{ fontFamily: "PJS-SemiBold", fontSize: 15, color: "#14233A" }}>Your Travel. Your Driver. Your Way.</Text>
      </View>
      <View testID="splash-road" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: ROAD, backgroundColor: "#3A4656", overflow: "hidden" }}>
        <View style={{ height: 6, backgroundColor: "#E9D9B6" }} />
        <Animated.View style={[{ position: "absolute", top: ROAD / 2, flexDirection: "row", gap: 30, width: width + 120 }, lines]}>
          {Array.from({ length: Math.ceil(width / 60) + 2 }).map((_, i) => <View key={i} style={{ width: 30, height: 5, borderRadius: 3, backgroundColor: "#fff" }} />)}
        </Animated.View>
      </View>
      <Animated.View testID="splash-car" style={[{ position: "absolute", bottom: ROAD - 58, left: 0 }, car]}>
        <Ionicons name="car-sport" size={84} color="#1E73E8" />
      </Animated.View>
    </Animated.View>
  );
}
