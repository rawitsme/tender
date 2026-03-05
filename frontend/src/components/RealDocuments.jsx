import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, FileText, CheckCircle, AlertCircle, Loader, Calendar, IndianRupee, Building, MapPin, Clock, ArrowLeft, BookOpen, Star, Users, Shield, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../api/client';

// Map source to portal key
const SOURCE_TO_PORTAL = {
  'UTTARAKHAND': 'uttarakhand',
  'UP': 'up',
  'MAHARASHTRA': 'maharashtra',
  'HARYANA': 'haryana',
  'MP': 'mp',
};

const RealDocuments = ({ tenderId, tenderTitle, source, tender }) => {
  const navigate = useNavigate();
  const [status, setStatus] = useState('checking');
  const [documents, setDocuments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [previousPath, setPreviousPath] = useState(null);

  // Detailed summary state
  const [detailedSummary, setDetailedSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);
  const [summaryExpanded, setSummaryExpanded] = useState(true);

  const portal = SOURCE_TO_PORTAL[source?.toUpperCase()];
  const isSupported = !!portal;

  useEffect(() => {
    // Remember where the user came from
    setPreviousPath(document.referrer || null);
    if (!isSupported) {
      setStatus('unsupported');
      return;
    }
    checkStatus();
  }, [tenderId, source]);

  const checkStatus = async () => {
    try {
      setStatus('checking');
      const sourceId = tender?.tender_id || tender?.source_id || tenderId;
      const resp = await api.get(`/real-docs/status/${encodeURIComponent(sourceId)}?portal=${portal}`);
      if (resp.data.status === 'downloaded') {
        setDocuments(resp.data.documents || []);
        setSummary(resp.data.summary);
        setStatus('downloaded');
      } else if (resp.data.status === 'downloading') {
        setStatus('downloading');
        setTimeout(checkStatus, 5000);
      } else {
        setStatus('not_downloaded');
      }
    } catch (err) {
      setStatus('not_downloaded');
    }
  };

  const startDownload = async () => {
    try {
      setStatus('downloading');
      setError(null);
      const sourceId = tender?.tender_id || tender?.source_id || tenderId;
      const resp = await api.post(`/real-docs/download/${encodeURIComponent(sourceId)}?portal=${portal}&title=${encodeURIComponent(tenderTitle || '')}`);
      
      if (resp.data.status === 'already_downloaded') {
        setDocuments(resp.data.documents || []);
        setSummary(resp.data.summary);
        setStatus('downloaded');
      } else {
        pollStatus(sourceId);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Download failed');
      setStatus('error');
    }
  };

  const pollStatus = (sourceId) => {
    const interval = setInterval(async () => {
      try {
        const resp = await api.get(`/real-docs/status/${encodeURIComponent(sourceId)}?portal=${portal}`);
        if (resp.data.status === 'downloaded') {
          clearInterval(interval);
          setDocuments(resp.data.documents || []);
          setSummary(resp.data.summary);
          setStatus('downloaded');
        } else if (resp.data.status === 'not_downloaded') {
          clearInterval(interval);
          setStatus('error');
          setError('Download may have failed. Try again.');
        }
      } catch {
        // Keep polling
      }
    }, 5000);
    
    setTimeout(() => {
      clearInterval(interval);
      if (status === 'downloading') {
        setStatus('error');
        setError('Download timed out. The portal may be slow. Try again.');
      }
    }, 180000);
  };

  const fetchDetailedSummary = async () => {
    try {
      setSummaryLoading(true);
      setSummaryError(null);
      const sourceId = tender?.tender_id || tender?.source_id || tenderId;
      const resp = await api.get(`/real-docs/detailed-summary/${encodeURIComponent(sourceId)}?portal=${portal}`);
      setDetailedSummary(resp.data.summary);
      setSummaryExpanded(true);
    } catch (err) {
      setSummaryError(err.response?.data?.detail || 'Failed to generate summary');
    } finally {
      setSummaryLoading(false);
    }
  };

  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/search');
    }
  };

  const getFileIcon = (name) => {
    if (name?.endsWith('.pdf')) return '📄';
    if (name?.endsWith('.xls') || name?.endsWith('.xlsx')) return '📊';
    if (name?.endsWith('.doc') || name?.endsWith('.docx')) return '📝';
    if (name?.endsWith('.zip')) return '📦';
    return '📄';
  };

  const formatSize = (bytes) => {
    if (bytes > 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} bytes`;
  };

  if (!isSupported) {
    return (
      <div className="bg-gray-50 rounded-xl border p-5">
        <h3 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
          <FileText size={18} /> Tender Documents
        </h3>
        <p className="text-sm text-gray-500">
          Document download is currently supported for NIC state portals (Uttarakhand, UP, Maharashtra, Haryana, MP).
          {source === 'GEM' && ' For GEM tenders, documents can be accessed directly from the GeM portal.'}
          {source === 'CPPP' && ' For CPPP tenders, documents can be accessed from the Central Public Procurement Portal.'}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <FileText size={18} /> Real Tender Documents
        </h3>
        {/* Go Back Button — always visible */}
        <button
          onClick={goBack}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          <ArrowLeft size={14} /> Go Back
        </button>
      </div>

      {/* Download Button / Status */}
      {status === 'checking' && (
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <Loader size={16} className="animate-spin" /> Checking for documents...
        </div>
      )}

      {status === 'not_downloaded' && (
        <div>
          <p className="text-sm text-gray-600 mb-3">
            Download the actual tender documents (NIT, BOQ, specifications) from the {SOURCE_TO_PORTAL[source?.toUpperCase()] ? source : 'government'} portal.
          </p>
          <button
            onClick={startDownload}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
          >
            <Download size={16} /> Get Real Documents
          </button>
          <p className="text-xs text-gray-400 mt-2">
            This will navigate to the portal, solve CAPTCHAs, and download all available documents. Takes 1-2 minutes.
          </p>
        </div>
      )}

      {status === 'downloading' && (
        <div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-800 font-medium text-sm">
              <Loader size={16} className="animate-spin" /> Downloading documents...
            </div>
            <p className="text-xs text-blue-600 mt-1">
              Navigating to portal, solving CAPTCHAs, and downloading files. This takes 1-2 minutes.
              You can browse other pages — the download continues in the background.
            </p>
            <div className="mt-2 h-1.5 bg-blue-200 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full animate-pulse" style={{ width: '60%' }} />
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
            <ArrowLeft size={12} /> Use <button onClick={goBack} className="text-primary-600 hover:underline font-medium">Go Back</button> to return to your previous screen. Downloads won't be lost.
          </p>
        </div>
      )}

      {status === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-800 font-medium text-sm">
            <AlertCircle size={16} /> {error || 'Download failed'}
          </div>
          <button
            onClick={startDownload}
            className="mt-2 flex items-center gap-2 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
          >
            <Download size={14} /> Try Again
          </button>
        </div>
      )}

      {status === 'downloaded' && (
        <div>
          {/* Quick Summary Card */}
          {summary && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 text-green-800 font-medium text-sm mb-3">
                <CheckCircle size={16} /> Documents Downloaded Successfully
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                {summary.published_date && (
                  <div className="flex items-start gap-2">
                    <Calendar size={14} className="text-gray-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-gray-500">Published:</span>{' '}
                      <span className="font-medium">{summary.published_date}</span>
                    </div>
                  </div>
                )}
                {summary.bid_submission_end && (
                  <div className="flex items-start gap-2">
                    <Clock size={14} className="text-red-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-gray-500">Last Date:</span>{' '}
                      <span className="font-medium text-red-700">{summary.bid_submission_end}</span>
                    </div>
                  </div>
                )}
                {summary.emd_amount && (
                  <div className="flex items-start gap-2">
                    <IndianRupee size={14} className="text-green-600 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-gray-500">EMD:</span>{' '}
                      <span className="font-medium">₹{summary.emd_amount}</span>
                    </div>
                  </div>
                )}
                {summary.organization && (
                  <div className="flex items-start gap-2 md:col-span-2">
                    <Building size={14} className="text-gray-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-gray-500">Organization:</span>{' '}
                      <span className="font-medium">{summary.organization}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Document Files */}
          <div className="space-y-2 mb-4">
            {documents.map((doc, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="text-lg">{getFileIcon(doc.name)}</span>
                  <div>
                    <p className="font-medium text-sm text-gray-900">{doc.name}</p>
                    <p className="text-xs text-gray-500">{formatSize(doc.size)}</p>
                  </div>
                </div>
                <a
                  href={`${api.defaults.baseURL}/real-docs/file/${encodeURIComponent(tender?.tender_id || tender?.source_id || tenderId)}/${encodeURIComponent(doc.name)}?portal=${portal}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-xs font-medium"
                >
                  <Download size={14} /> Download
                </a>
              </div>
            ))}
          </div>

          {/* Get Detailed Summary Button */}
          {!detailedSummary && (
            <button
              onClick={fetchDetailedSummary}
              disabled={summaryLoading}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed w-full justify-center"
            >
              {summaryLoading ? (
                <>
                  <Loader size={16} className="animate-spin" /> Generating Summary...
                </>
              ) : (
                <>
                  <BookOpen size={16} /> Get Detailed Summary
                </>
              )}
            </button>
          )}

          {summaryError && (
            <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
              <AlertCircle size={14} className="inline mr-1" /> {summaryError}
            </div>
          )}

          {/* Detailed Summary — One Pager */}
          {detailedSummary && (
            <div className="mt-4 bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-200 rounded-xl overflow-hidden">
              {/* Header */}
              <button
                onClick={() => setSummaryExpanded(!summaryExpanded)}
                className="w-full flex items-center justify-between p-4 hover:bg-indigo-100/30 transition-colors"
              >
                <h4 className="font-bold text-indigo-900 flex items-center gap-2">
                  <BookOpen size={18} /> Tender Summary — One Pager
                </h4>
                {summaryExpanded ? <ChevronUp size={18} className="text-indigo-600" /> : <ChevronDown size={18} className="text-indigo-600" />}
              </button>

              {summaryExpanded && (
                <div className="px-4 pb-4 space-y-4">
                  {/* Tender Details */}
                  <div className="bg-white rounded-lg p-4 border border-indigo-100">
                    <h5 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-sm">
                      <FileText size={14} className="text-indigo-600" /> Tender Details
                    </h5>
                    <p className="text-sm text-gray-800 font-medium">{detailedSummary.tender_title}</p>
                    {detailedSummary.tender_id && (
                      <p className="text-xs text-gray-500 mt-1 font-mono">ID: {detailedSummary.tender_id}</p>
                    )}
                    {detailedSummary.tender_type && (
                      <p className="text-xs text-gray-500 mt-0.5">Type: {detailedSummary.tender_type}</p>
                    )}
                  </div>

                  {/* Agency + Dates Row */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Publishing Agency */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100">
                      <h5 className="font-semibold text-gray-900 mb-1 flex items-center gap-2 text-sm">
                        <Building size={14} className="text-indigo-600" /> Publishing Agency
                      </h5>
                      <p className="text-sm text-gray-700">{detailedSummary.publishing_agency || 'Not specified'}</p>
                    </div>

                    {/* Key Dates */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100">
                      <h5 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-sm">
                        <Calendar size={14} className="text-indigo-600" /> Key Dates
                      </h5>
                      <div className="space-y-1.5 text-sm">
                        {detailedSummary.published_date && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Published:</span>
                            <span className="font-medium">{detailedSummary.published_date}</span>
                          </div>
                        )}
                        {detailedSummary.last_date && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Last Date:</span>
                            <span className="font-bold text-red-700">{detailedSummary.last_date}</span>
                          </div>
                        )}
                        {detailedSummary.pre_bid_date && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Pre-Bid Meeting:</span>
                            <span className="font-medium text-blue-700">{detailedSummary.pre_bid_date}</span>
                          </div>
                        )}
                        {detailedSummary.bid_opening_date && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Bid Opening:</span>
                            <span className="font-medium">{detailedSummary.bid_opening_date}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Financials Row */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {/* EMD */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100 text-center">
                      <p className="text-xs text-gray-500 mb-1">EMD</p>
                      <p className="text-lg font-bold text-green-700">{detailedSummary.emd || 'N/A'}</p>
                    </div>
                    {/* Estimated Value */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100 text-center">
                      <p className="text-xs text-gray-500 mb-1">Estimated Value</p>
                      <p className="text-lg font-bold text-indigo-700">
                        {detailedSummary.estimated_value || 'N/A'}
                      </p>
                      {detailedSummary.estimated_value_note && (
                        <p className="text-xs text-amber-600 mt-1 flex items-center justify-center gap-1">
                          <Star size={10} className="fill-amber-500" /> {detailedSummary.estimated_value_note}
                        </p>
                      )}
                    </div>
                    {/* Tender Fee */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100 text-center">
                      <p className="text-xs text-gray-500 mb-1">Tender Fee</p>
                      <p className="text-lg font-bold text-gray-700">{detailedSummary.tender_fee || 'N/A'}</p>
                    </div>
                  </div>

                  {/* Scope of Work */}
                  <div className="bg-white rounded-lg p-4 border border-indigo-100">
                    <h5 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-sm">
                      <FileText size={14} className="text-indigo-600" /> Brief Scope of Work
                    </h5>
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                      {detailedSummary.scope_of_work || 'Refer tender documents'}
                    </p>
                  </div>

                  {/* Eligibility Criteria */}
                  <div className="bg-white rounded-lg p-4 border border-indigo-100">
                    <h5 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-sm">
                      <Shield size={14} className="text-indigo-600" /> Eligibility Criteria
                    </h5>
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                      {detailedSummary.eligibility_criteria || 'Refer tender documents'}
                    </p>
                  </div>

                  {/* JV Allowed */}
                  <div className="bg-white rounded-lg p-4 border border-indigo-100">
                    <h5 className="font-semibold text-gray-900 mb-2 flex items-center gap-2 text-sm">
                      <Users size={14} className="text-indigo-600" /> Joint Venture (JV)
                    </h5>
                    <p className="text-sm font-medium">
                      {detailedSummary.jv_allowed || 'Not specified'}
                    </p>
                  </div>

                  {/* Documents List */}
                  {detailedSummary.documents?.length > 0 && (
                    <div className="text-xs text-gray-500 pt-2 border-t border-indigo-100">
                      <span className="font-medium">Source Documents:</span>{' '}
                      {detailedSummary.documents.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RealDocuments;
