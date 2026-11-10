// Multipart upload that works in BOTH runtimes. Use this for every file upload; never
// build the FormData part yourself.
//
// Native (iOS/Android): files are read with the expo-file-system `File` class, which expo/fetch
// and native upload tasks understand directly. (Wrapping a fetched blob in `new Blob([...])`
// fails on real phones; that was the cause of driver uploads breaking outside the web preview.)
// Web: the browser picker returns blob:/data: URLs that the browser fetch can read.

import { File, UploadType } from "expo-file-system";
import { fetch as expoFetch } from "expo/fetch";
import { Platform } from "react-native";

export type LocalFile = {
  uri: string; // asset.uri from expo-image-picker / expo-document-picker / expo-image-manipulator
  name?: string;
  mimeType?: string;
};

export type UploadOptions = {
  files: Record<string, LocalFile>;
  fields?: Record<string, string>;
  method?: "POST" | "PUT";
  headers?: Record<string, string>; // auth only; never Content-Type
  signal?: AbortSignal;
};

export function fileNameFor(file: LocalFile): string {
  return file.name || file.uri.split("?")[0].split("/").pop() || "file";
}

export async function uploadForm(url: string, opts: UploadOptions): Promise<Response> {
  const form = new FormData();
  for (const [k, v] of Object.entries(opts.fields ?? {})) form.append(k, v);
  for (const [field, file] of Object.entries(opts.files)) {
    if (Platform.OS === "web") {
      const blob = await (await fetch(file.uri)).blob();
      form.append(field, file.mimeType && file.mimeType !== blob.type ? new Blob([blob], { type: file.mimeType }) : blob, fileNameFor(file));
    } else {
      form.append(field, new File(file.uri) as any);
    }
  }
  const init = { method: opts.method ?? "POST", body: form, headers: opts.headers, signal: opts.signal };
  return Platform.OS === "web" ? fetch(url, init) : (expoFetch(url, init as any) as unknown as Promise<Response>);
}

export type UploadResult = { status: number; body: string };

/** Single-file multipart upload with byte progress (0..1). Native uses a native upload task; web uses XHR. */
export async function uploadWithProgress(
  url: string,
  file: LocalFile,
  opts: { headers?: Record<string, string>; fieldName?: string; onProgress?: (p: number) => void },
): Promise<UploadResult> {
  const field = opts.fieldName ?? "file";
  if (Platform.OS !== "web") {
    const task = new File(file.uri).createUploadTask(url, {
      httpMethod: "POST",
      uploadType: UploadType.MULTIPART,
      fieldName: field,
      mimeType: file.mimeType,
      headers: opts.headers,
      onProgress: ({ bytesSent, totalBytes }) => totalBytes > 0 && opts.onProgress?.(Math.min(1, bytesSent / totalBytes)),
    });
    const r = await task.uploadAsync();
    if (!r) throw new Error("Upload was cancelled");
    return { status: r.status, body: r.body };
  }
  const blob = await (await fetch(file.uri)).blob();
  const part = file.mimeType && file.mimeType !== blob.type ? new Blob([blob], { type: file.mimeType }) : blob;
  const form = new FormData();
  form.append(field, part, fileNameFor(file));
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    for (const [k, v] of Object.entries(opts.headers ?? {})) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => e.lengthComputable && opts.onProgress?.(e.loaded / e.total);
    xhr.onload = () => resolve({ status: xhr.status, body: xhr.responseText });
    xhr.onerror = () => reject(new Error("Network error. Check your connection and try again."));
    xhr.ontimeout = () => reject(new Error("The upload timed out. Please try again."));
    xhr.timeout = 120000;
    xhr.send(form);
  });
}
