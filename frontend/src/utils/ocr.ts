import Tesseract from 'tesseract.js';

export type OCRResult = {
  text: string;
  confidence: number;
  error?: string;
};

/**
 * Extract text from an image using Tesseract.js OCR
 * @param imageUri - URI of the image to process
 * @returns OCR result with extracted text and confidence score
 */
export async function extractTextFromImage(imageUri: string): Promise<OCRResult> {
  try {
    console.log('Starting OCR for image:', imageUri);
    
    const result = await Tesseract.recognize(
      imageUri,
      'eng', // English language
      {
        logger: (m: any) => {
          if (m.status === 'recognizing text') {
            console.log(`OCR Progress: ${(m.progress * 100).toFixed(0)}%`);
          }
        },
      }
    );
    
    console.log('OCR completed with confidence:', result.data.confidence);
    
    return {
      text: result.data.text,
      confidence: result.data.confidence,
    };
  } catch (error) {
    console.error('OCR Error:', error);
    return {
      text: '',
      confidence: 0,
      error: error instanceof Error ? error.message : 'OCR failed',
    };
  }
}

/**
 * Extract driving licence information from OCR text
 * @param ocrText - Raw OCR text from licence image
 * @returns Extracted licence details
 */
export function extractLicenceInfo(ocrText: string) {
  const text = ocrText.toUpperCase();
  
  // Extract licence number (Indian format: KA0120200001234)
  const licenceNoMatch = text.match(/[A-Z]{2}\d{2}\d{4}\d{7}/);
  const licenceNo = licenceNoMatch ? licenceNoMatch[0] : null;
  
  // Extract expiry date (DD-MM-YYYY or DD/MM/YYYY format)
  const expiryMatch = text.match(/\d{2}[-\/]\d{2}[-\/]\d{4}/);
  const expiry = expiryMatch ? expiryMatch[0].replace(/\//g, '-') : null;
  
  // Extract name (usually the first line before licence number)
  const lines = text.split('\n').filter(line => line.trim().length > 0);
  const name = lines[0]?.replace(/[^A-Z\s]/g, '').trim() || null;
  
  // Extract vehicle class (MCWG, LMV, etc.)
  const vehicleClassMatch = text.match(/MCWG|LMV|MGV|HMV|TRAILER/i);
  const vehicleClass = vehicleClassMatch ? vehicleClassMatch[0].toUpperCase() : null;
  
  return {
    licenceNo,
    expiry,
    name,
    vehicleClass,
  };
}

/**
 * Extract RC information from OCR text
 * @param ocrText - Raw OCR text from RC image
 * @returns Extracted RC details
 */
export function extractRCInfo(ocrText: string) {
  const text = ocrText.toUpperCase();
  
  // Extract RC number (Indian format: KA01AB1234)
  const rcNoMatch = text.match(/[A-Z]{2}\d{2}[A-Z]{2}\d{4}/);
  const rcNo = rcNoMatch ? rcNoMatch[0] : null;
  
  // Extract registration date
  const regDateMatch = text.match(/\d{2}[-\/]\d{2}[-\/]\d{4}/);
  const regDate = regDateMatch ? regDateMatch[0].replace(/\//g, '-') : null;
  
  // Extract vehicle class
  const vehicleClassMatch = text.match(/MCWG|LMV|MGV|HMV|TRAILER/i);
  const vehicleClass = vehicleClassMatch ? vehicleClassMatch[0].toUpperCase() : null;
  
  // Extract fuel type
  const fuelMatch = text.match(/PETROL|DIESEL|CNG|ELECTRIC|LPG/i);
  const fuelType = fuelMatch ? fuelMatch[0].toUpperCase() : null;
  
  return {
    rcNo,
    regDate,
    vehicleClass,
    fuelType,
  };
}
