import React, { useState, useEffect } from 'react';
import { Download, FileText, ExternalLink, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { api } from '../api';

const RealDocuments = ({ tenderId, tenderTitle, source }) => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [status, setStatus] = useState('not_checked'); // not_checked, found, not_found, downloading, error
  const [error, setError] = useState(null);

  // Check for existing documents on component mount
  useEffect(() => {
    checkExistingDocuments();
  }, [tenderId]);

  const checkExistingDocuments = async () => {
    try {
      const response = await api.get(`/real-docs/list/${tenderId}`);
      
      if (response.data.status === 'found') {
        setDocuments(response.data.files);
        setStatus('found');
      } else {
        setStatus('not_found');
      }
    } catch (err) {
      console.warn('Error checking documents:', err);
      setStatus('not_found');
    }
  };

  const downloadRealDocuments = async () => {
    setDownloading(true);
    setError(null);
    setStatus('downloading');

    try {
      const response = await api.post(`/real-docs/download/${tenderId}`);
      
      if (response.data.status === 'success') {
        setDocuments(response.data.files);
        setStatus('found');
        // Refresh the list to get updated info
        setTimeout(checkExistingDocuments, 1000);
      } else {
        setError(response.data.message || 'No documents could be downloaded');
        setStatus('error');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to download documents');
      setStatus('error');
    } finally {
      setDownloading(false);
    }
  };

  const downloadFile = async (filename) => {
    try {
      window.open(`/api/v1/real-docs/file/${tenderId}/${filename}`, '_blank');
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes > 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    } else if (bytes > 1024) {
      return `${(bytes / 1024).toFixed(0)} KB`;
    }
    return `${bytes} bytes`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <FileText className="w-6 h-6 text-blue-600" />
        <h3 className="text-lg font-semibold text-gray-900">
          Real Tender Documents
        </h3>
      </div>

      <div className="text-sm text-gray-600 mb-4">
        Download actual PDF documents (NIT, BOQ, Technical Specs) directly from the government portal
      </div>

      {/* Status Display */}
      {status === 'found' && (
        <div className="flex items-center gap-2 text-green-700 bg-green-50 p-3 rounded-lg mb-4">
          <CheckCircle className="w-5 h-5" />
          <span>Documents available for download</span>
        </div>
      )}

      {status === 'downloading' && (
        <div className="flex items-center gap-2 text-blue-700 bg-blue-50 p-3 rounded-lg mb-4">
          <Loader className="w-5 h-5 animate-spin" />
          <span>Downloading documents from {source} portal...</span>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center gap-2 text-red-700 bg-red-50 p-3 rounded-lg mb-4">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Documents List */}
      {documents.length > 0 && (
        <div className="space-y-3 mb-4">
          {documents.map((doc, index) => (
            <div 
              key={index}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-red-600" />
                <div>
                  <div className="font-medium text-gray-900">{doc.filename}</div>
                  <div className="text-sm text-gray-500">
                    PDF Document • {formatFileSize(doc.size)}
                  </div>
                </div>
              </div>
              
              <button
                onClick={() => downloadFile(doc.filename)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-3">
        {(status === 'not_found' || status === 'not_checked') && (
          <button
            onClick={downloadRealDocuments}
            disabled={downloading}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 transition-colors"
          >
            {downloading ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {downloading ? 'Downloading...' : 'Get Real Documents'}
          </button>
        )}

        {status === 'found' && (
          <button
            onClick={downloadRealDocuments}
            disabled={downloading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
          >
            <Download className="w-4 h-4" />
            Refresh Documents
          </button>
        )}

        {status === 'error' && (
          <button
            onClick={downloadRealDocuments}
            disabled={downloading}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            Try Again
          </button>
        )}
      </div>

      {/* Info Footer */}
      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
        <div className="text-sm text-blue-800">
          <strong>What you get:</strong> Actual tender documents including Notice Inviting Tender (NIT), 
          Bill of Quantities (BOQ), Technical Specifications, Terms & Conditions, and other attachments 
          required for bidding.
        </div>
      </div>
    </div>
  );
};

export default RealDocuments;