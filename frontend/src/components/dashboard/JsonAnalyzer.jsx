import React, { useState } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function JsonAnalyzer() {
  const [jsonInput, setJsonInput] = useState(`{
  "channel": "email",
  "recipient": "customer@example.com",
  "template_id": "welcome_email",
  "variables": {
    "name": "Jane Doe",
    "activation_link": "https://senderx.io/verify"
  }
}`);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const { showToast } = useToast();

  const handleAnalyze = async () => {
    let parsed;
    try {
      parsed = JSON.parse(jsonInput);
    } catch (e) {
      showToast('Invalid JSON syntax: ' + e.message, 'error');
      return;
    }

    setIsAnalyzing(true);
    try {
      const res = await ApiClient.analyzeJson(parsed);
      if (res?.success) {
        setAnalysisResult(res.data);
        showToast('JSON Payload analyzed successfully!', 'success');
      } else {
        setAnalysisResult(res);
        showToast(res?.message || 'Validation returned issues', 'warning');
      }
    } catch (err) {
      showToast(err?.message || 'Error analyzing payload', 'error');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <h3 style={{ fontSize: '1.05rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
        Dynamic Ingestion Payload Sandbox & Analyzer
      </h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        Validate payload schemas, channel attributes, and variable dictionaries prior to dispatching from your external microservices.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.25rem' }}>
        <div>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', display: 'block' }}>
            Inbound Payload (JSON)
          </label>
          <textarea
            className="form-control"
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            rows={10}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.85rem',
              background: 'var(--bg-main)',
            }}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            style={{ marginTop: '0.75rem' }}
          >
            {isAnalyzing ? 'Analyzing Schema...' : 'Analyze & Validate Schema'}
          </button>
        </div>

        <div>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', display: 'block' }}>
            Analysis & Routing Report
          </label>
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--glass-border)',
              borderRadius: '6px',
              padding: '1rem',
              minHeight: '235px',
              fontSize: '0.85rem',
            }}
          >
            {analysisResult ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.75rem' }}>
                  <span className={`badge ${analysisResult.is_valid || analysisResult.valid ? 'badge-success' : 'badge-danger'}`}>
                    {analysisResult.is_valid || analysisResult.valid ? 'SCHEMA VALID' : 'SCHEMA INVALID'}
                  </span>
                  {analysisResult.channel && (
                    <span className="badge badge-info">Channel: {analysisResult.channel}</span>
                  )}
                </div>

                {analysisResult.errors && analysisResult.errors.length > 0 && (
                  <div style={{ color: 'var(--status-error)', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 600 }}>Detected Schema Violations:</div>
                    <ul style={{ paddingLeft: '1.25rem', margin: '0.25rem 0' }}>
                      {analysisResult.errors.map((err, i) => (
                        <li key={i}>{typeof err === 'string' ? err : JSON.stringify(err)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <div>Detected Keys: <code>{Object.keys(analysisResult.detected_fields || {}).join(', ') || 'Standard keys'}</code></div>
                  <div style={{ marginTop: '4px' }}>Routing Engine: Celery Ingestion Pipeline</div>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: '3rem' }}>
                Run analysis to inspect schema compliance, target channel routing, and variable extraction.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
