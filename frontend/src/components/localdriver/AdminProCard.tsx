import { Image } from "expo-image";
import React, { useState } from "react";
import { Pressable, View } from "react-native";

import { fileUrl } from "@/src/api";
import { COMMERCIAL, ITEM_LABEL, PRO_STATUS } from "@/src/components/localdriver/parts";
import { Badge, Btn, Card, Chip, Field, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const DOCS = [["licence_front", "Licence front"], ["licence_back", "Licence back"], ["id_proof", "Aadhaar front"]] as const;
const fmt = (iso: string) => new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Admin review of one local driver: documents, decision with reason + items, vehicle approval, suspend, availability, earnings. */
export function AdminProCard({ p, act, onPreview }: { p: any; act: (path: string, body?: any, method?: string) => void; onPreview: (uri: string) => void }) {
  const { colors } = useTheme();
  const [note, setNote] = useState("");
  const [items, setItems] = useState<string[]>([]);
  const photos = p.documents?.photos ?? {};
  const st = PRO_STATUS[p.status] ?? PRO_STATUS.under_review;
  const review = (decision: string) => act(`/admin/pro-drivers/${p.user_id}/review`, { decision, note, items });
  return (
    <Card testID={`admin-pro-${p.user_id}`} style={{ gap: space.sm }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
        <T weight="800" style={{ flex: 1 }}>{p.name} · {p.email}</T>
        <Badge testID={`admin-pro-status-${p.user_id}`} label={p.suspended ? "Suspended" : st.label} tone={p.suspended ? "error" : st.tone} />
      </View>
      <T size={12}>Phone {p.phone || "—"} · Carpool verification: {p.carpool_status}</T>
      <View style={{ flexDirection: "row", gap: space.sm }}>
        {DOCS.map(([k, l]) => {
          const fid = photos[k] ?? (k !== "id_proof" ? photos.licence : undefined);
          return (
            <Pressable key={k} testID={`admin-pro-doc-${k}-${p.user_id}`} onPress={() => fid && onPreview(fileUrl(fid))} style={{ flex: 1, gap: 2 }}>
              <View style={{ height: 64, borderRadius: 8, overflow: "hidden", backgroundColor: colors.surfaceTertiary }}>
                {fid ? <Image source={{ uri: fileUrl(fid) }} style={{ width: "100%", height: "100%" }} contentFit="cover" /> : null}
              </View>
              <T size={10} color={colors.muted}>{l}{fid ? "" : " (missing)"}</T>
            </Pressable>
          );
        })}
      </View>
      <T size={12}>Licence {p.licence_no} · valid until {p.licence_expiry}</T>
      <T size={12}>Home: {p.home ? `${p.home.subdistrict_name} ${p.home.sub_label}, ${p.home.district_name}, ${p.home.state_name}` : "not set"}{p.home?.geo ? " · location pinned" : ""}</T>
      <T size={12}>Languages: {(p.languages ?? []).join(", ")}</T>
      <View style={{ flexDirection: "row", gap: space.xs, flexWrap: "wrap" }}>
        {(p.services ?? ["rent"]).map((s: string) => <Badge key={s} testID={`admin-pro-service-${s}-${p.user_id}`} label={s === "book" ? "Book a Driver" : "Rent a Driver"} tone="info" />)}
        <Badge testID={`admin-pro-avail-${p.user_id}`} label={p.availability_status === "available" ? "ONLINE" : "OFFLINE"} tone={p.availability_status === "available" ? "success" : "muted"} />
        <Badge label={p.acceptOutstationTrips ? "Outstation on" : "Local only"} tone="muted" />
      </View>
      {(p.availability ?? []).filter((a: any) => new Date(a.to) > new Date()).map((a: any) => <T key={a.id} size={11} color={colors.muted}>Available {fmt(a.from)} → {fmt(a.to)}</T>)}
      <T size={12} color={colors.muted}>{p.completed_trips} completed trips · ₹{p.earnings_total} earned</T>
      {(p.shared_vehicles ?? []).map((v: any) => {
        const c = COMMERCIAL[v.commercial_status ?? "none"] ?? COMMERCIAL.none;
        return (
          <View key={v.vehicle_id} testID={`admin-pro-vehicle-${v.vehicle_id}`} style={{ gap: 4, padding: space.sm, borderRadius: 8, backgroundColor: colors.surfaceTertiary }}>
            <T size={12} weight="700">{v.name || `${v.make} ${v.model}`} · {v.reg_no} · {v.vtype} · {v.seats} seats</T>
            <T size={11} color={colors.muted}>Permit {v.permit_no || "—"} · Insurance till {v.insurance_expiry || "—"} · ₹{v.day_rate || 0}/day</T>
            <View style={{ flexDirection: "row", gap: space.xs, alignItems: "center", flexWrap: "wrap" }}>
              <Badge label={c.label} tone={c.tone} />
              {v.rc_file_id ? <Btn small variant="ghost" label="View RC" onPress={() => onPreview(fileUrl(v.rc_file_id))} testID={`admin-vehicle-rc-${v.vehicle_id}`} /> : null}
              {v.commercial_status === "pending" ? <>
                <Btn small testID={`admin-vehicle-approve-${v.vehicle_id}`} label="Approve vehicle" onPress={() => act(`/admin/vehicles/${v.vehicle_id}/commercial`, { decision: "approved", note })} />
                <Btn small variant="danger" testID={`admin-vehicle-reject-${v.vehicle_id}`} label="Reject" onPress={() => act(`/admin/vehicles/${v.vehicle_id}/commercial`, { decision: "rejected", note: note || "Documents not valid" })} />
              </> : null}
            </View>
          </View>
        );
      })}
      {p.admin_note ? <T size={12} color={colors.muted}>Last note: {p.admin_note}</T> : null}
      {["under_review", "approved"].includes(p.status) ? (
        <View style={{ gap: space.sm }}>
          <Field testID={`admin-pro-note-${p.user_id}`} placeholder="Reason / note for the driver" value={note} onChangeText={setNote} maxLength={500} />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
            {Object.entries(ITEM_LABEL).map(([k, l]) => <Chip key={k} testID={`admin-pro-item-${k}-${p.user_id}`} label={l} active={items.includes(k)} onPress={() => setItems(items.includes(k) ? items.filter((x) => x !== k) : [...items, k])} />)}
          </View>
          <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
            {p.status === "under_review" ? <Btn small testID={`admin-pro-approve-${p.user_id}`} label="Approve" onPress={() => review("approved")} /> : null}
            <Btn small variant="outline" testID={`admin-pro-resubmit-${p.user_id}`} label="Request resubmission" onPress={() => review("resubmit")} />
            <Btn small variant="danger" testID={`admin-pro-reject-${p.user_id}`} label="Reject" onPress={() => review("rejected")} />
          </View>
        </View>
      ) : null}
      <Btn small variant={p.suspended ? "primary" : "ghost"} testID={`admin-pro-suspend-${p.user_id}`} label={p.suspended ? "Reactivate driver" : "Suspend driver"}
        onPress={() => act(`/admin/pro-drivers/${p.user_id}/suspend`, { suspended: !p.suspended, note })} />
    </Card>
  );
}
