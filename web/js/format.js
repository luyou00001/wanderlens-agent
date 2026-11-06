export const STATS = [
  ["assets", "素材"],
  ["images", "照片"],
  ["videos", "影片"],
  ["described", "已有畫面描述"],
  ["needs_vision", "待視覺模型"],
  ["drafted", "已有草稿"],
  ["approved", "已核准發佈"],
  ["cleared", "已標記可販售"],
  ["with_gps", "含定位"],
  ["decode_errors", "無法解碼"],
  ["trips", "行程"],
];

const ROLES = {
  vision_language: "視覺描述",
  video_understanding: "影片理解",
  shot_detection: "鏡頭切分",
  speech_transcription: "語音轉錄",
  image_embedding: "影像特徵",
  text_embedding: "文字特徵",
  aesthetic_quality: "美學分數",
  image_restoration: "影像修復",
  image_generation: "影像生成",
  image_editing: "影像編修",
  video_generation: "影片生成",
  matting: "去背",
  text_generation: "文字生成",
  audio_generation: "聲音生成",
  audio_understanding: "聲音理解",
  ocr: "文字辨識",
  pose: "姿態",
  privacy_redaction: "隱私遮罩",
};

const COMMERCIAL = {
  allowed: "可商用",
  disallowed: "不可商用",
  conditional: "附條件",
  unknown: "未確認",
};

const STATUS = {
  recommended: "預設",
  alternate: "備選",
  "catalog-only": "已收錄",
  restricted: "限制使用",
};

export function roleLabel(role) {
  return ROLES[role] || role;
}

export function commercialLabel(value) {
  return COMMERCIAL[value] || value || "未確認";
}

export function statusLabel(value) {
  return STATUS[value] || value || "未分類";
}

export function commercialTone(value) {
  if (value === "allowed") return "tag-ok";
  if (value === "disallowed") return "tag-danger";
  if (value === "conditional") return "tag-warn";
  return "tag-muted";
}

export function mediaLabel(value) {
  if (value === "image") return "照片";
  if (value === "video") return "影片";
  return "其他";
}

export function providerLabel(value) {
  if (value === "openai") return "視覺模型";
  if (value === "heuristic") return "技術預檢";
  return "尚未描述";
}

export function peopleLabel(value) {
  if (value === true) return "有可辨識人物";
  if (value === false) return "無可辨識人物";
  return "人物尚未判斷";
}

export function when(value) {
  if (!value) return "沒有拍攝時間";
  const text = String(value);
  if (text.length >= 16 && text[4] === "-" && text[10] === "T") {
    return text.slice(0, 16).replace("T", " ");
  }
  return text;
}

export function clock(date) {
  const pad = (number) => String(number).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function bytes(value) {
  const size = Number(value);
  if (!Number.isFinite(size)) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}

export function count(value) {
  const number = Number(value);
  return Number.isFinite(number) ? String(number) : "0";
}
