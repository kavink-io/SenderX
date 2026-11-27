const generatedAvatarCache = new Map();
const ageGroups = new Set(['under_18', '18_25', '26_35', '36_45', '46_60', 'over_60']);
const backgrounds = ['#e7ebf7', '#e7f0ef', '#f1e9e2', '#e9e8f4', '#e8eef2'];
const clothingColors = ['#34415c', '#36515a', '#4b4568', '#45505a', '#475b71'];

function hash(value) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function normalizeGender(gender) {
  if (typeof gender !== 'string') return null;
  const normalized = gender.trim().toLowerCase();
  return ['male', 'female', 'non-binary', 'prefer not to say', 'other'].includes(normalized)
    ? normalized
    : null;
}

function parseBirthDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }
  if (typeof value !== 'string') return null;

  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const [, year, month, day] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    parsed.getFullYear() !== Number(year)
    || parsed.getMonth() !== Number(month) - 1
    || parsed.getDate() !== Number(day)
  ) return null;
  return parsed;
}

export function getEmployeeAge(employee, today = new Date()) {
  const dateOfBirth = employee?.date_of_birth || employee?.birth_date || employee?.dob;
  if (dateOfBirth) {
    const birthDate = parseBirthDate(dateOfBirth);
    if (birthDate && birthDate <= today) {
      let age = today.getFullYear() - birthDate.getFullYear();
      if (
        today.getMonth() < birthDate.getMonth()
        || (today.getMonth() === birthDate.getMonth() && today.getDate() < birthDate.getDate())
      ) age -= 1;
      if (age >= 0) return age;
    }
  }

  if (employee?.age === undefined || employee?.age === null || employee.age === '') return null;
  const existingAge = Number(employee?.age);
  return Number.isInteger(existingAge) && existingAge >= 0 ? existingAge : null;
}

export function getEmployeeAgeGroup(employee, today = new Date()) {
  const age = getEmployeeAge(employee, today);
  if (age === null) return null;
  if (age < 18) return 'under_18';
  if (age <= 25) return '18_25';
  if (age <= 35) return '26_35';
  if (age <= 45) return '36_45';
  if (age <= 60) return '46_60';
  return 'over_60';
}

export function getUploadedAvatar(employee) {
  const candidates = [
    employee?.avatar_url,
    employee?.profile_photo_url,
    employee?.profile_picture_url,
    employee?.profile_image_url,
    employee?.photo_url,
    employee?.profile_photo,
    employee?.profile_picture,
    employee?.avatar,
  ];

  for (const candidate of candidates) {
    const value = typeof candidate === 'string'
      ? candidate
      : candidate && typeof candidate === 'object'
        ? candidate.url || candidate.src
        : null;
    const url = typeof value === 'string' ? value.trim() : '';
    if (url) return url;
  }
  return null;
}

function getLocalProfile(employee) {
  const id = employee?.user_id || employee?.id || employee?._id;
  const storageKey = id ? `senderx:professional-avatar:${id}` : null;
  if (storageKey && typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) {
        const profile = JSON.parse(saved);
        if (profile?.seed) return profile;
      }
    } catch {
      // Use the deterministic fallback when local storage is unavailable or invalid.
    }
  }

  const identity = String(id || employee?.email || employee?.name || 'senderx-user');
  const profile = {
    version: 1,
    seed: hash(identity).toString(16),
    gender: normalizeGender(employee?.gender),
    age_group: getEmployeeAgeGroup(employee),
  };
  if (storageKey && typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(profile));
    } catch {
      return profile;
    }
  }
  return profile;
}

function generateAvatar(profile) {
  const gender = normalizeGender(profile.gender) || 'unspecified';
  const ageGroup = ageGroups.has(profile.age_group) ? profile.age_group : null;
  const key = `${profile.version || 1}:${profile.seed}:${gender}:${ageGroup || 'generic'}`;
  if (generatedAvatarCache.has(key)) return generatedAvatarCache.get(key);

  const variation = hash(`${profile.seed}:${gender}`);
  const background = backgrounds[variation % backgrounds.length];
  const clothing = clothingColors[(variation >>> 4) % clothingColors.length];
  const hairstyle = variation % 3;
  const hair = ageGroup === 'over_60'
    ? '#9297a1'
    : ageGroup === '46_60'
      ? '#686c78'
      : '#343744';
  const hairShapes = [
    '<path d="M27 43c-2-17 7-29 21-29 16 0 24 11 22 29-5-5-7-11-8-16-8 7-19 10-34 10l-1 6z"/>',
    '<path d="M25 42c0-17 8-28 23-28 16 0 24 11 23 28l-3 15-6-4 1-16c-9 5-20 7-36 6v14l-5 1z"/>',
    '<path d="M28 42c-1-18 7-28 20-28 15 0 23 10 21 28-5-2-8-6-10-12-8 6-17 8-30 8z"/><circle cx="31" cy="27" r="4"/><circle cx="39" cy="17" r="4"/><circle cx="51" cy="14" r="4"/><circle cx="63" cy="19" r="4"/>',
  ];
  const youth = ageGroup === 'under_18';
  const hairShape = hairShapes[hairstyle];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
    <defs><clipPath id="crop"><circle cx="48" cy="48" r="48"/></clipPath></defs>
    <g clip-path="url(#crop)">
      <rect width="96" height="96" fill="${background}"/>
      <path d="M10 100c2-20 16-31 38-31s36 11 38 31" fill="${clothing}"/>
      <path d="m38 67 10 10 10-10 5 4-9 25H42l-9-25z" fill="#f3f4f6"/>
      <path d="M40 56h16v16c-4 6-12 6-16 0z" fill="#d9aa87"/>
      <ellipse cx="48" cy="42" rx="${youth ? 15 : 17}" ry="${youth ? 19 : 21}" fill="#e8bd9d"/>
      <g fill="${hair}">${hairShape}</g>
      <path d="M36 42h5M55 42h5" stroke="#42424a" stroke-width="2" stroke-linecap="round"/>
      <path d="M48 44v7" stroke="#c08d70" stroke-width="1.5" stroke-linecap="round"/>
      <path d="M43 56c3 2 7 2 10 0" fill="none" stroke="#9e5e5b" stroke-width="1.8" stroke-linecap="round"/>
      ${ageGroup === 'over_60' ? '<path d="M35 51h5m16 0h5" stroke="#c79b80" stroke-width="1" stroke-linecap="round"/>' : ''}
    </g>
  </svg>`;
  const avatar = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  generatedAvatarCache.set(key, avatar);
  return avatar;
}

export function getProfessionalAvatar(employee) {
  const profile = employee?.avatar_profile?.seed
    ? employee.avatar_profile
    : getLocalProfile(employee);
  return generateAvatar(profile);
}
