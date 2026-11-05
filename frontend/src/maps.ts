import { Linking } from "react-native";

/** Opens the route in Google Maps (no API key needed). Fallback when no in-app map provider is configured. */
export function openRouteInMaps(trip: any) {
  const wp = (trip.stops || []).map((s: any) => `${s.lat},${s.lng}`).join("|");
  const url = `https://www.google.com/maps/dir/?api=1&origin=${trip.origin.lat},${trip.origin.lng}&destination=${trip.destination.lat},${trip.destination.lng}${wp ? `&waypoints=${encodeURIComponent(wp)}` : ""}&travelmode=driving`;
  Linking.openURL(url);
}
