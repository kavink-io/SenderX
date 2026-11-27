import React from 'react';
import { GlassSelect } from '../glass';

export const GENDER_OPTIONS = [
  'Male',
  'Female',
  'Non-binary',
  'Prefer not to say',
  'Other',
];

export default function GenderSelect({ id, value, onChange }) {
  return (
    <div className="form-group">
      <label htmlFor={id}>Gender</label>
      <GlassSelect id={id} value={value || ''} onChange={onChange}>
        <option value="">Select gender</option>
        {GENDER_OPTIONS.map((gender) => (
          <option value={gender} key={gender}>{gender}</option>
        ))}
      </GlassSelect>
    </div>
  );
}
