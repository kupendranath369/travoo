import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, Switch, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, fileUrl, Loc, locPayload } from "@/src/api";
import { useAuth } from "@/src/auth";
import { LocationField } from "@/src/components/LocationField";
import { MapDataCard } from "@/src/components/MapDataCard";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Empty, ErrorBox, Field, Header, Loading, Section, Stepper, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const TABS = ["overview", "drivers", "pro", "places", "users", "trips", "bookings", "tickets", "reviews", "routes", "settings"] as const;
type Tab = (typeof TABS)[number];
const PATH: Record<Tab, string> = { overview: "/admin/stats", drivers: "/admin/drivers", pro: "/admin/pro-drivers", places: "/admin/locations/missing", users: "/admin/users", trips: "/admin/trips", bookings: "/admin/bookings", tickets: "/admin/tickets", reviews: "/admin/reviews", routes: "/routes/popular", settings: "/admin/settings" };

export default function AdminScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<any>(null);
  const [dataTab, setDataTab] = useState<Tab | null>(null);
  const [err, setErr] = useState("");
  const [dStatus, setDStatus] = useState("under_review");
  const [q, setQ] = useState("");
  const [rFrom, setRFrom] = useState<Loc | null>(null);
  const [rTo, setRTo] = useState<Loc | null>(null);
  const [rPrice, setRPrice] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [fuel, setFuel] = useState<Record<string, string>>({});
  useEffect(() => {
    if (tab === "settings") api("/fuel-prices").then((r) => setFuel(Object.fromEntries(Object.entries(r.prices).map(([k, v]: any) => [k, String(v.price)])))).catch(() => {});
  }, [tab]);

  const load = useCallback(async () => {
    setErr("");
    try {
      const path = tab === "drivers" || tab === "pro" ? `${PATH[tab]}?status=${dStatus}` : tab === "users" ? `${PATH.users}?q=${encodeURIComponent(q)}` : PATH[tab];
      const res = await api(path);
      setData(res);
      setDataTab(tab);
    } catch (e: any) {
      setErr(e.message);
    }
  }, [tab, dStatus, q]);
  useEffect(() => { setData(null); load(); }, [load]);

  const act = async (path: string, body: any = {}, method = "POST") => {
    try {
      await api(path, { method, body: method === "DELETE" ? undefined : body });
      toast("Done");
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  if (user?.role !== "admin") return <View style={{ flex: 1 }}><Header title={t("admin.title")} /><Empty icon="lock-closed" title="Admin access required" /></View>;

  const stat = (k: string, v: any, id: string) => (
    <Card key={k} style={{ width: "47%", flexGrow: 1, padding: space.md, gap: 2 }}>
      <T size={11} color={colors.muted}>{t(k)}</T>
      <T testID={id} size={20} weight="800">{v}</T>
    </Card>
  );

  const body = () => {
    if (err) return <ErrorBox message={err} onRetry={load} />;
    if (!data || dataTab !== tab) return <Loading />;
    switch (tab) {
      case "overview":
        return (
          <>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
              {stat("admin.stat.users", data.users, "admin-stat-users")}
              {stat("admin.stat.passengers", data.passengers, "admin-stat-passengers")}
              {stat("admin.stat.drivers", data.drivers, "admin-stat-drivers")}
              {stat("admin.stat.verified", data.verified, "admin-stat-verified")}
              {stat("admin.stat.pending", data.pending, "admin-stat-pending")}
              {stat("admin.stat.trips", data.trips, "admin-stat-trips")}
              {stat("admin.stat.active", data.active, "admin-stat-active")}
              {stat("admin.stat.bookings", data.bookings, "admin-stat-bookings")}
              {stat("admin.stat.completed", data.completed, "admin-stat-completed")}
              {stat("admin.stat.cancelled", data.cancelled, "admin-stat-cancelled")}
              {stat("admin.stat.value", inr(data.value), "admin-stat-value")}
              {stat("admin.stat.earnings", inr(data.earnings), "admin-stat-earnings")}
            </View>
            <T size={12} color={colors.muted}>{t("admin.not_revenue")}</T>
            <Section title={t("admin.monthly")}>
              {data.monthly.map((m: any) => {
                const max = Math.max(...data.monthly.map((x: any) => x.bookings), 1);
                return (
                  <View key={m._id} style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
                    <T size={12} style={{ width: 64 }}>{m._id}</T>
                    <View style={{ flex: 1, height: 14, backgroundColor: colors.surfaceTertiary, borderRadius: 7, overflow: "hidden" }}>
                      <View style={{ width: `${(m.bookings / max) * 100}%`, height: "100%", backgroundColor: colors.brandPrimary }} />
                    </View>
                    <T size={12} weight="700">{m.bookings} / {m.completed}✓</T>
                  </View>
                );
              })}
            </Section>
            <Section title={t("admin.top_drivers")}>
              {data.top_drivers.length === 0 ? <T color={colors.muted}>{t("admin.empty")}</T> : null}
              {data.top_drivers.map((d: any) => (
                <View key={d._id} style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <T>{d.name} · {d.trips} trips</T>
                  <T weight="800">{inr(d.v)}</T>
                </View>
              ))}
            </Section>
            <Section title={t("home.popular")}>
              {data.top_routes.map((r: any) => <T key={r._id} size={13}>{r._id} — {r.n}</T>)}
            </Section>
            <MapDataCard />
            <Section title="User growth">
              {data.growth.map((g: any) => <T key={g._id} size={13}>{g._id}: +{g.users}</T>)}
            </Section>
          </>
        );
      case "drivers":
        return (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
              {["under_review", "approved", "rejected", "resubmit"].map((s) => <Chip key={s} testID={`admin-driver-filter-${s}`} label={t(`verify.status.${s}`)} active={dStatus === s} onPress={() => setDStatus(s)} />)}
            </ScrollView>
            <Field testID="admin-review-note" placeholder={t("verify.admin_note")} value={note} onChangeText={setNote} />
            {data.length === 0 ? <Empty title={t("admin.empty")} /> : null}
            {data.map((u: any) => (
              <Card key={u.user_id} testID={`admin-driver-${u.user_id}`} style={{ gap: space.sm }}>
                <T weight="800">{u.name} · {u.email}</T>
                <View style={{ flexDirection: "row", gap: space.sm }}>
                  {["profile", "licence", "rc", "vehicle"].map((k) => (
                    <Pressable key={k} testID={`admin-doc-${k}-${u.user_id}`} onPress={() => u.documents?.photos?.[k] && setPreview(fileUrl(u.documents.photos[k]))} style={{ flex: 1, aspectRatio: 1, borderRadius: 8, overflow: "hidden", backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
                      {u.documents?.photos?.[k] ? <Image source={{ uri: fileUrl(u.documents.photos[k]) }} style={{ width: "100%", height: "100%" }} contentFit="cover" /> : <Ionicons name="image-outline" size={18} color={colors.muted} />}
                      <View style={{ position: "absolute", bottom: 0, left: 0, right: 0, backgroundColor: colors.brand, paddingVertical: 2 }}>
                        <T size={10} weight="700" color={colors.onBrand} center numberOfLines={1} adjustsFontSizeToFit>{t(`verify.photo.${k}`)}</T>
                      </View>
                    </Pressable>
                  ))}
                </View>
                {u.documents?.vehicle_name ? <T size={12}>{t("verify.vehicle_name")}: {u.documents.vehicle_name}</T> : null}
                <T size={12}>{t("verify.legal_name")}: {u.documents?.legal_name} · {u.documents?.phone}</T>
                <T size={12}>{t("verify.licence")}: {u.documents?.licence_no} (till {u.documents?.licence_expiry})</T>
                <T size={12}>{t("verify.rc")}: {u.documents?.rc_no}</T>
                <T size={12} color={colors.muted}>{u.vehicles.map((v: any) => `${v.make} ${v.model} ${v.reg_no}`).join(", ") || "No vehicles"}</T>
                <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
                  <Btn small testID={`admin-approve-${u.user_id}`} label={t("admin.approve")} onPress={() => act(`/admin/drivers/${u.user_id}/review`, { decision: "approved", note })} />
                  <Btn small variant="danger" testID={`admin-reject-${u.user_id}`} label={t("admin.reject")} onPress={() => act(`/admin/drivers/${u.user_id}/review`, { decision: "rejected", note })} />
                  <Btn small variant="outline" testID={`admin-resubmit-${u.user_id}`} label={t("admin.resubmit")} onPress={() => act(`/admin/drivers/${u.user_id}/review`, { decision: "resubmit", note })} />
                </View>
              </Card>
            ))}
          </>
        );
      case "pro":
        return (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
              {["under_review", "approved", "rejected", "resubmit"].map((s) => <Chip key={s} testID={`admin-pro-filter-${s}`} label={t(`verify.status.${s}`)} active={dStatus === s} onPress={() => setDStatus(s)} />)}
            </ScrollView>
            {data.length === 0 ? <Empty title={t("admin.empty")} /> : null}
            {data.map((p: any) => (
              <Card key={p.user_id} testID={`admin-pro-${p.user_id}`} style={{ gap: space.sm }}>
                <T weight="800">{p.name} · {p.email}</T>
                <View style={{ flexDirection: "row", gap: space.sm }}>
                  {["profile", "licence"].map((k) => (
                    <Pressable key={k} testID={`admin-pro-doc-${k}-${p.user_id}`} onPress={() => p.documents?.photos?.[k] && setPreview(fileUrl(p.documents.photos[k]))} style={{ width: 72, height: 72, borderRadius: 8, overflow: "hidden", backgroundColor: colors.surfaceTertiary }}>
                      {p.documents?.photos?.[k] ? <Image source={{ uri: fileUrl(p.documents.photos[k]) }} style={{ width: "100%", height: "100%" }} contentFit="cover" /> : null}
                    </Pressable>
                  ))}
                </View>
                <T size={12}>{p.city?.name} · {p.experience_years}y · {p.languages.join(", ")} · {p.vehicle_types.join(", ")}</T>
                <T size={12}>{t("verify.licence")}: {p.licence_no} ({p.licence_expiry})</T>
                <T size={12} color={colors.muted}>₹{p.rate_hourly}/h · ₹{p.rate_half_day} · ₹{p.rate_full_day} · {p.bio}</T>
                {p.status === "under_review" ? (
                  <View style={{ flexDirection: "row", gap: space.sm }}>
                    <Btn small testID={`admin-pro-approve-${p.user_id}`} label={t("admin.approve")} onPress={() => act(`/admin/pro-drivers/${p.user_id}/review`, { decision: "approved", note })} />
                    <Btn small variant="danger" testID={`admin-pro-reject-${p.user_id}`} label={t("admin.reject")} onPress={() => act(`/admin/pro-drivers/${p.user_id}/review`, { decision: "rejected", note })} />
                  </View>
                ) : null}
              </Card>
            ))}
          </>
        );
      case "places":
        return data.length === 0 ? <Empty title={t("admin.empty")} /> : data.map((r: any) => (
          <Card key={r.request_id} testID={`admin-place-${r.request_id}`} style={{ gap: 4, padding: space.md }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="800" style={{ flex: 1 }}>{r.name} {r.local_name ? `(${r.local_name})` : ""}</T>
              <Badge label={r.status} tone={statusTone(r.status === "pending" ? "pending" : r.status)} />
            </View>
            <T size={12}>{r.ltype} · {r.district}, {r.state} {r.pin ?? ""} · {r.lat.toFixed(5)}, {r.lng.toFixed(5)}</T>
            <T size={11} color={colors.muted}>{r.user_name}</T>
            {r.status === "pending" ? (
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <Btn small testID={`admin-place-approve-${r.request_id}`} label={t("admin.approve")} onPress={() => act(`/admin/locations/missing/${r.request_id}`, { decision: "approved" })} />
                <Btn small variant="outline" testID={`admin-place-reject-${r.request_id}`} label={t("admin.reject")} onPress={() => act(`/admin/locations/missing/${r.request_id}`, { decision: "rejected" })} />
              </View>
            ) : null}
          </Card>
        ));
      case "users":
        return (
          <>
            <Field testID="admin-user-search" placeholder="Search name or email" value={q} onChangeText={setQ} autoCapitalize="none" />
            {data.map((u: any) => (
              <Card key={u.user_id} testID={`admin-user-${u.user_id}`} style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md }}>
                <View style={{ flex: 1 }}>
                  <T weight="700">{u.name} {u.role === "admin" ? "(admin)" : ""}</T>
                  <T size={12} color={colors.muted}>{u.email} · {t(`verify.status.${u.driver_status}`)} · {u.language}</T>
                </View>
                {u.role !== "admin" ? <Btn small variant={u.suspended ? "primary" : "danger"} testID={`admin-suspend-${u.user_id}`} label={u.suspended ? t("admin.unsuspend") : t("admin.suspend")} onPress={() => act(`/admin/users/${u.user_id}/suspend`, { suspended: !u.suspended })} /> : null}
              </Card>
            ))}
          </>
        );
      case "trips":
        return data.map((tr: any) => (
          <Card key={tr.trip_id} testID={`admin-trip-${tr.trip_id}`} onPress={() => router.push(`/trip/${tr.trip_id}`)} style={{ gap: 4, padding: space.md }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700" style={{ flex: 1 }}>{tr.origin.name} → {tr.destination.name}</T>
              <Badge label={t(`status.${tr.status}`)} tone={statusTone(tr.status)} />
            </View>
            <T size={12} color={colors.muted}>{tr.driver?.name} · {fmtDate(tr.date)} {tr.time} · {inr(tr.price)} · {tr.seats_total - tr.seats_available}/{tr.seats_total} {tr.is_demo ? "· DEMO" : ""}</T>
            {tr.status === "scheduled" ? <Btn small variant="ghost" testID={`admin-cancel-trip-${tr.trip_id}`} label={t("trip.cancel")} onPress={() => act(`/trips/${tr.trip_id}/cancel`, { reason: "Cancelled by admin" })} /> : null}
          </Card>
        ));
      case "bookings":
        return data.length === 0 ? <Empty title={t("admin.empty")} /> : data.map((b: any) => (
          <Card key={b.booking_id} testID={`admin-booking-${b.booking_id}`} onPress={() => router.push(`/booking/${b.booking_id}`)} style={{ gap: 4, padding: space.md }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700">{b.booking_id}</T>
              <Badge label={t(`status.${b.status}`)} tone={statusTone(b.status)} />
            </View>
            <T size={12} color={colors.muted}>{b.route} · {b.date} · {b.seats} seats · {inr(b.fare_total)} · {b.settlement?.status}</T>
            {b.status === "cancelled" ? <T size={12} color={colors.error}>{b.cancelled_by}: {b.cancel_reason}</T> : null}
          </Card>
        ));
      case "tickets":
        return data.length === 0 ? <Empty title={t("admin.empty")} /> : data.map((k: any) => (
          <Card key={k.ticket_id} testID={`admin-ticket-${k.ticket_id}`} style={{ gap: 4, padding: space.md, borderColor: k.priority === "high" ? colors.error : colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700" style={{ flex: 1 }}>{k.ticket_id} · {k.type} · {k.subject}</T>
              <Badge label={k.status} tone={k.status === "resolved" ? "success" : "warning"} />
            </View>
            <T size={12}>{k.message}</T>
            <T size={11} color={colors.muted}>{k.user_name} {k.booking_id ? `· ${k.booking_id}` : ""}</T>
            {k.status === "open" ? <Btn small variant="outline" testID={`admin-resolve-${k.ticket_id}`} label={t("admin.resolve")} onPress={() => act(`/admin/tickets/${k.ticket_id}/resolve`)} /> : null}
          </Card>
        ));
      case "reviews":
        return data.length === 0 ? <Empty title={t("admin.empty")} /> : data.map((r: any) => (
          <Card key={r.review_id} testID={`admin-review-${r.review_id}`} style={{ gap: 4, padding: space.md, opacity: r.hidden ? 0.5 : 1 }}>
            <T weight="700">{"★".repeat(r.rating)} · {r.reviewer_name} → {r.role}</T>
            <T size={12}>{r.comment}</T>
            {!r.hidden ? <Btn small variant="ghost" testID={`admin-hide-review-${r.review_id}`} label={t("admin.delete")} onPress={() => act(`/admin/reviews/${r.review_id}`, {}, "DELETE")} /> : null}
          </Card>
        ));
      case "routes":
        return (
          <>
            <Card style={{ gap: space.sm }}>
              <LocationField testID="admin-route-from" label={t("search.from")} value={rFrom} onChange={setRFrom} />
              <LocationField testID="admin-route-to" label={t("search.to")} value={rTo} onChange={setRTo} />
              <Field testID="admin-route-price" label={t("offer.price")} value={rPrice} onChangeText={(x) => setRPrice(x.replace(/\D/g, ""))} keyboardType="number-pad" />
              <Btn testID="admin-add-route-button" small label={t("admin.add_route")} disabled={!rFrom || !rTo || !rPrice} onPress={() => act("/admin/routes", { origin: locPayload(rFrom!), destination: locPayload(rTo!), price_hint: Number(rPrice) })} />
            </Card>
            {data.map((r: any) => (
              <Card key={r.route_id} testID={`admin-route-${r.route_id}`} style={{ flexDirection: "row", alignItems: "center", padding: space.md }}>
                <T weight="700" style={{ flex: 1 }}>{r.origin.name} → {r.destination.name} · {inr(r.price_hint)}</T>
                <Btn small variant="ghost" icon="trash-outline" testID={`admin-del-route-${r.route_id}`} label="" onPress={() => act(`/admin/routes/${r.route_id}`, {}, "DELETE")} />
              </Card>
            ))}
          </>
        );
      case "settings":
        return (
          <Card style={{ gap: space.lg }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
              <View style={{ flex: 1 }}>
                <T weight="800">{t("admin.instant_approval")}</T>
                <T size={12} color={colors.muted}>{t("admin.instant_approval_d")}</T>
              </View>
              <Switch testID="admin-instant-approval-switch" value={!!data.instant_driver_approval} onValueChange={(v) => act("/admin/settings", { instant_driver_approval: v }, "PUT")} trackColor={{ true: colors.brandTertiary, false: colors.border }} />
            </View>
            <View style={{ gap: space.sm }}>
              <T size={13} weight="600">{t("admin.cancel_hours")}</T>
              <Stepper testID="admin-cancel-hours" min={0} max={72} value={data.passenger_cancel_hours ?? 6} onChange={(v) => act("/admin/settings", { passenger_cancel_hours: v }, "PUT")} />
            </View>
            <View style={{ gap: space.sm }}>
              <T size={13} weight="600">{t("admin.driver_cancel_hours")}</T>
              <Stepper testID="admin-driver-cancel-hours" min={0} max={72} value={data.driver_cancel_hours ?? 12} onChange={(v) => act("/admin/settings", { driver_cancel_hours: v }, "PUT")} />
            </View>
            <View style={{ gap: space.sm }}>
              <T weight="800">{t("v2.fuel_prices")} (₹)</T>
              {["petrol", "diesel", "cng", "electric"].map((ft) => (
                <View key={ft} style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
                  <T style={{ width: 80 }}>{ft.toUpperCase()}</T>
                  <View style={{ flex: 1 }}><Field testID={`admin-fuel-${ft}`} placeholder={ft === "electric" ? "₹/kWh" : ft === "cng" ? "₹/kg" : "₹/litre"} value={fuel[ft] ?? ""} onChangeText={(v) => setFuel({ ...fuel, [ft]: v.replace(/[^\d.]/g, "") })} keyboardType="decimal-pad" /></View>
                  <Btn small testID={`admin-fuel-save-${ft}`} label={t("common.save")} disabled={!fuel[ft]} onPress={() => act("/admin/fuel-prices", { state: "default", fuel_type: ft, price: Number(fuel[ft]) })} />
                </View>
              ))}
              <T size={11} color={colors.muted}>National default. Update regularly from official oil-company / state rates.</T>
            </View>
            <View style={{ gap: space.sm }}>
              <T size={13} weight="600">{t("v2.maintenance")}</T>
              <Stepper testID="admin-maint" min={0} max={20} value={Math.round(data.maintenance_per_km ?? 2)} onChange={(v) => act("/admin/settings", { maintenance_per_km: v }, "PUT")} />
            </View>
            <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
              <Ionicons name="information-circle-outline" size={18} color={colors.muted} />
              <T size={12} color={colors.muted} style={{ flex: 1 }}>Languages: 23 enabled (22 professionally reviewed). Locations: 36 states/UTs + starter places, OpenStreetMap search for the rest.</T>
            </View>
          </Card>
        );
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("admin.title")} />
      <View style={{ height: 56, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm, paddingHorizontal: space.lg, alignItems: "center" }}>
          {TABS.map((k) => <Chip key={k} testID={`admin-tab-${k}`} label={t(`admin.${k}`)} active={tab === k} onPress={() => setTab(k)} />)}
        </ScrollView>
      </View>
      <ScrollView testID="admin-content" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>{body()}</ScrollView>
      <Modal visible={!!preview} transparent animationType="fade" onRequestClose={() => setPreview(null)}>
        <Pressable testID="admin-doc-preview" onPress={() => setPreview(null)} style={{ flex: 1, backgroundColor: colors.surfaceInverse, alignItems: "center", justifyContent: "center", padding: space.lg }}>
          {preview ? <Image source={{ uri: preview }} style={{ width: "100%", height: "80%" }} contentFit="contain" /> : null}
          <T color={colors.onSurfaceInverse} weight="700">{t("common.close")}</T>
        </Pressable>
      </Modal>
    </View>
  );
}
