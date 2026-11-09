import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Field, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function ManualVerificationScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const { user } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ legal_name: "", vehicle_name: "", phone: "", licence_no: "", licence_expiry: "", rc_no: "" });
  const [profilePhoto, setProfilePhoto] = useState<string | null>(null);
  const [licenceFront, setLicenceFront] = useState<string | null>(null);
  const [licenceBack, setLicenceBack] = useState<string | null>(null);
  const [rcPhoto, setRcPhoto] = useState<string | null>(null);
  const [vehiclePhoto, setVehiclePhoto] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    if (f.legal_name.trim().length < 3) return setErr("Legal name required");
    if (f.vehicle_name.trim().length < 2) return setErr("Vehicle name required");
    if (!/^[6-9]\d{9}$/.test(f.phone)) return setErr("Valid phone number required");
    if (f.licence_no.replace(/\s/g, "").length < 8) return setErr("Licence number required");
    if (!/^\d{2}-\d{2}-\d{4}$/.test(f.licence_expiry)) return setErr("Valid expiry date required (DD-MM-YYYY)");
    if (f.rc_no.replace(/\s/g, "").length < 6) return setErr("RC number required");
    if (!profilePhoto || !licenceFront || !licenceBack || !rcPhoto || !vehiclePhoto) return setErr("All photos required");
    
    setBusy("submit");
    setErr("");
    try {
      const r = await api("/driver/verification", { body: { ...f, licence_no: f.licence_no.replace(/\s/g, ""), rc_no: f.rc_no.replace(/\s/g, "") } });
      toast(t(`verify.status.${r.status}`));
      router.back();
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy("");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Manual Verification" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.md }}>
          <T weight="800">Upload Documents for Manual Verification</T>
          <T size={12} color={colors.muted}>Admins will manually review your documents for verification</T>
          
          <View style={{ gap: space.sm }}>
            <T size={13} weight="700">Profile Photo</T>
            <Btn variant="outline" label={profilePhoto ? "Uploaded" : "Upload Profile Photo"} onPress={() => setProfilePhoto("temp_fid")} />
          </View>
          
          <View style={{ gap: space.sm }}>
            <T size={13} weight="700">Driving Licence (Front)</T>
            <Btn variant="outline" label={licenceFront ? "Uploaded" : "Upload Licence Front"} onPress={() => setLicenceFront("temp_fid")} />
          </View>
          
          <View style={{ gap: space.sm }}>
            <T size={13} weight="700">Driving Licence (Back)</T>
            <Btn variant="outline" label={licenceBack ? "Uploaded" : "Upload Licence Back"} onPress={() => setLicenceBack("temp_fid")} />
          </View>
          
          <View style={{ gap: space.sm }}>
            <T size={13} weight="700">RC Document</T>
            <Btn variant="outline" label={rcPhoto ? "Uploaded" : "Upload RC"} onPress={() => setRcPhoto("temp_fid")} />
          </View>
          
          <View style={{ gap: space.sm }}>
            <T size={13} weight="700">Vehicle Photo</T>
            <Btn variant="outline" label={vehiclePhoto ? "Uploaded" : "Upload Vehicle Photo"} onPress={() => setVehiclePhoto("temp_fid")} />
          </View>
        </Card>
        
        <Card style={{ gap: space.md }}>
          <T weight="800">Document Details</T>
          <Field label="Legal Name" value={f.legal_name} onChangeText={(x) => setF({ ...f, legal_name: x })} />
          <Field label="Vehicle Name" value={f.vehicle_name} onChangeText={(x) => setF({ ...f, vehicle_name: x })} placeholder="Maruti Suzuki Dzire" />
          <Field label="Phone" value={f.phone} onChangeText={(x) => setF({ ...f, phone: x.replace(/\D/g, "") })} keyboardType="phone-pad" maxLength={10} />
          <Field label="Licence Number" value={f.licence_no} onChangeText={(x) => setF({ ...f, licence_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA0120200001234" />
          <Field label="Licence Expiry" value={f.licence_expiry} onChangeText={(x) => setF({ ...f, licence_expiry: x })} placeholder="31-12-2035" maxLength={10} />
          <Field label="RC Number" value={f.rc_no} onChangeText={(x) => setF({ ...f, rc_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA01AB1234" />
        </Card>
        
        {err ? <T color={colors.error} weight="700">{err}</T> : null}
        <Btn label="Submit for Manual Verification" onPress={submit} loading={busy === "submit"} />
        <Btn variant="ghost" label="Cancel" onPress={() => router.back()} />
      </KeyboardAwareScrollView>
    </View>
  );
}
