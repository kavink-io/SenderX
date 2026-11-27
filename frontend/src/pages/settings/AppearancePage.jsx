import React from 'react';
import AppearanceSettings from '../../components/settings/AppearanceSettings';

export default function AppearancePage() {
  return (
    <section className="tab-pane active" aria-labelledby="appearance-page-title">
      <header className="appearance-page-header">
        <h1 id="appearance-page-title">Appearance &amp; Layout</h1>
        <p>Personalize your SenderX workspace. Changes apply immediately and are saved to your user account.</p>
      </header>
      <AppearanceSettings />
    </section>
  );
}
