export interface Project {
  name: string;
  description: string;
  url: string;
  host: string;
  icon: string;
}

// In the order they were built. Addresses are the apps' production URLs; icons are the apps' own app icons (public/project-icons, 120px).
export const PROJECTS: Project[] = [
  { name: "My Duolingo", description: "간격 반복으로 익히는 영어 표현 카드", url: "https://my-duoringo.vercel.app", host: "my-duoringo.vercel.app", icon: "/project-icons/my-duoringo.png" },
  { name: "RichRich", description: "개인 투자 브리핑 대시보드", url: "https://richrich-hj.vercel.app", host: "richrich-hj.vercel.app", icon: "/project-icons/richrich.png" },
  { name: "APT Leader", description: "수도권 대장 아파트를 내 집과 비교", url: "https://apt-leader.vercel.app", host: "apt-leader.vercel.app", icon: "/project-icons/apt-leader.png" },
  { name: "Weekend Kid", description: "광교에서 차로 90분, 이번 주말 아이와 갈 곳", url: "https://weekend-kid.vercel.app", host: "weekend-kid.vercel.app", icon: "/project-icons/weekend-kid.png" },
  { name: "Let's eat", description: "평일 저녁·주말 끼니를 짜주는 가족 식단표", url: "https://kid-meal.vercel.app", host: "kid-meal.vercel.app", icon: "/project-icons/kid-meal.png" },
  { name: "OOTD Lab", description: "오늘 날씨에 맞는 가족 코디 추천", url: "https://closet-mix.vercel.app", host: "closet-mix.vercel.app", icon: "/project-icons/closet-mix.png" },
];
