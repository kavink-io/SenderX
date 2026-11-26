import React, { useState } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { GlassCard, GlassButton, GlassBadge } from '../glass';

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
    <GlassCard style={{ marginTop: '1.35rem' }}>
      <h3 style={{ fontSize: '1.05rem', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
        Dynamic Ingestion Payload Sandbox &amp; Analyzer
      </h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        Validate payload schemas, channel attributes, and variable dictionaries prior to dispatching from your external microservices.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.25rem' }}>
        <div>
          <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.4rem', display: 'block', color: 'var(--text-secondary)' }}>
            Inbound Payload (JSON)
          </label>
          <textarea
            className="form-control lg-studio-editor"
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            rows={10}
          />
          <GlassButton
            variant="primary"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            style={{ marginTop: '0.75rem' }}
          >
            {isAnalyzing ? 'Analyzing Schema...' : 'Analyze & Validate Schema'}
          </GlassButton>
        </div>

        <div>
          <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.4rem', display: 'block', color: 'var(--text-secondary)' }}>
            Analysis &amp; Routing Report
          </label>
          <div
            className="lg-glass-inset"
            style={{
              padding: '1rem',
              minHeight: '235px',
              fontSize: '0.85rem',
            }}
          >
            {analysisResult ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.75rem' }}>
                  <GlassBadge tone={analysisResult.is_valid || analysisResult.valid ? 'success' : 'danger'}>
                    {analysisResult.is_valid || analysisResult.valid ? 'SCHEMA VALID' : 'SCHEMA INVALID'}
                  </GlassBadge>
                  {analysisResult.channel && (
                    <GlassBadge tone="info">Channel: {analysisResult.channel}</GlassBadge>
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
    </GlassCard>
  );
}
