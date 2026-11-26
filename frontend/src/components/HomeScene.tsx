import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import { useWindowDimensions, View } from "react-native";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";
import Svg, { Path } from "react-native-svg";

const NAVY = "#14243A";
const GOLD = "#C5A059";
const ROAD = 34;

function useLoop(to: number, duration: number) {
  const v = useSharedValue(0);
  useEffect(() => {
    v.value = withRepeat(withTiming(to, { duration, easing: Easing.linear }), -1);
  }, [v, to, duration]);
  return v;
}

/** Animated scene: a family travelling in a car along a hill road. */
export function TravelScene({ height }: { height: number }) {
  const { width } = useWindowDimensions();
  const road = useLoop(70, 600);
  const hills = useLoop(width, 16000);
  const clouds = useLoop(width + 160, 22000);
  const bob = useSharedValue(0);
  useEffect(() => {
    bob.value = withRepeat(withSequence(withTiming(-2.5, { duration: 220 }), withTiming(0, { duration: 220 })), -1);
  }, [bob]);
  const dashes = useAnimatedStyle(() => ({ transform: [{ translateX: road.value - 70 }] }));
  const hillsSt = useAnimatedStyle(() => ({ transform: [{ translateX: hills.value - width }] }));
  const cloudSt = useAnimatedStyle(() => ({ transform: [{ translateX: clouds.value - 160 }] }));
  const carSt = useAnimatedStyle(() => ({ transform: [{ translateY: bob.value }] }));
  const carW = Math.min(230, width * 0.56);
  const hill = `M0 60 Q ${width * 0.15} 10 ${width * 0.3} 45 T ${width * 0.6} 35 T ${width} 50 L ${width} 90 L 0 90 Z`;
  return (
    <View testID="home-travel-scene" pointerEvents="none" style={{ position: "absolute", left: 0, right: 0, top: 0, height, overflow: "hidden" }}>
      <LinearGradient colors={["#FAF6EE", "#F6EAD0", "#EFD9AE"]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <View style={{ position: "absolute", right: 36, top: height * 0.32, width: 46, height: 46, borderRadius: 23, backgroundColor: "#F2C46D", opacity: 0.85 }} />
      <Animated.View style={[{ position: "absolute", top: height * 0.26, flexDirection: "row", gap: 120 }, cloudSt]}>
        <Ionicons name="cloud" size={34} color="#FFFFFF" />
        <Ionicons name="cloud" size={24} color="#FFFFFF" style={{ marginTop: 18 }} />
      </Animated.View>
      <Animated.View style={[{ position: "absolute", bottom: ROAD - 4, flexDirection: "row", width: width * 2 }, hillsSt]}>
        {[0, 1].map((i) => (
          <Svg key={i} width={width} height={90}>
            <Path d={hill} fill={GOLD} opacity={0.35} />
            <Path d={`M0 80 Q ${width * 0.25} 40 ${width * 0.5} 70 T ${width} 65 L ${width} 90 L 0 90 Z`} fill={NAVY} opacity={0.18} />
          </Svg>
        ))}
      </Animated.View>
      <View testID="home-scene-road" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: ROAD, backgroundColor: NAVY, overflow: "hidden" }}>
        <View style={{ height: 3, backgroundColor: GOLD }} />
        <Animated.View style={[{ position: "absolute", top: ROAD / 2, flexDirection: "row", gap: 35, width: width + 140 }, dashes]}>
          {Array.from({ length: Math.ceil(width / 70) + 3 }).map((_, i) => <View key={i} style={{ width: 35, height: 4, borderRadius: 2, backgroundColor: GOLD }} />)}
        </Animated.View>
      </View>
      <Animated.View style={[{ position: "absolute", bottom: ROAD - 10, right: width * 0.08, width: carW, aspectRatio: 900 / 501 }, carSt]}>
        <Image testID="home-family-car" source={require("@/assets/images/family-car.png")} style={{ width: "100%", height: "100%" }} contentFit="contain" accessibilityLabel="Family travelling in a car" />
      </Animated.View>
    </View>
  );
}

/** Home service tile: illustration on top, navy band with gold accents. */
export function ServiceTile({ art, title, sub }: { art: number; title: string; sub: string }) {
  return (
    <View style={{ flex: 1, borderRadius: 22, backgroundColor: NAVY, borderWidth: 2, borderColor: GOLD, overflow: "hidden",
      shadowColor: NAVY, shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 5 }}>
      <Image source={art} style={{ width: "100%", aspectRatio: 392 / 218 }} contentFit="cover" />
      <Svg width="100%" height={22} viewBox="0 0 100 22" preserveAspectRatio="none" style={{ marginTop: -21 }}>
        <Path d="M0 12 Q 25 0 50 10 T 100 6 L 100 22 L 0 22 Z" fill={NAVY} />
        <Path d="M0 12 Q 25 0 50 10 T 100 6" stroke={GOLD} strokeWidth={1.2} fill="none" />
      </Svg>
      <View style={{ paddingHorizontal: 10, paddingBottom: 12, paddingTop: 2, alignItems: "center", gap: 2 }}>
        <Animated.Text numberOfLines={1} adjustsFontSizeToFit style={{ fontFamily: "PJS-ExtraBold", fontSize: 19, color: "#FFFFFF" }}>{title}</Animated.Text>
        <Animated.Text numberOfLines={1} adjustsFontSizeToFit style={{ fontFamily: "PJS-Bold", fontSize: 14, color: GOLD }}>{sub}</Animated.Text>
      </View>
    </View>
  );
}
