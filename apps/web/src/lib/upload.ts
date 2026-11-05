export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export const MAX_UPLOAD_LABEL = "25 MB";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function validateUploadFile(file: File): string | null {
  const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (suffix !== ".xlsx" && suffix !== ".csv") {
    return `${file.name} is not an .xlsx or .csv file.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return (
      `${file.name} is ${formatFileSize(file.size)}. ` +
      `Files must be ${MAX_UPLOAD_LABEL} or smaller.`
    );
  }
  return null;
}
