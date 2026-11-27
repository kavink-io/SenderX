import React from 'react';
import ProviderConfigSection from '../../components/settings/ProviderConfigSection';

export default function ChannelConfigurations() {
  return (
    <div className="tab-pane active" id="tab-org-channels">
      <div className="saas-report-heading">
        <div>
          <h1>Channel Configurations</h1>
          <p>Manage the organization-scoped providers SenderX uses for outbound messages.</p>
        </div>
      </div>
      <ProviderConfigSection />
    </div>
  );
}
