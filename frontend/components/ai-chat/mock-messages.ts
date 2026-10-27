import type { Message } from "./types";

export const MOCK_MESSAGES: Message[] = [
  {
    id: 1,
    role: "assistant",
    content: "Hi! I'm your AI assistant. How can I help you today?",
    time: "10:32 AM",
  },
  {
    id: 2,
    role: "user",
    content: "Show me some interesting places nearby.",
    time: "10:33 AM",
  },
  {
    id: 3,
    role: "assistant",
    content:
      "Sure. I can help you discover places, restaurants, landmarks, and other points of interest on the map.",
    time: "10:33 AM",
  },
  {
    id: 4,
    role: "user",
    content: "Can you filter by top-rated coffee shops in Manhattan?",
    time: "10:34 AM",
  },
  {
    id: 5,
    role: "assistant",
    content:
      "I found 8 top-rated coffee shops near your location. Highlighted on the map: Blue Bottle, Stumptown, and Devoción.",
    time: "10:34 AM",
  },
  {
    id: 6,
    role: "user",
    content: "Which one has the best seating area for working?",
    time: "10:35 AM",
  },
  {
    id: 7,
    role: "assistant",
    content:
      "Devoción on 20th Street has spacious seating with high ceilings and plenty of natural light, perfect for working.",
    time: "10:35 AM",
  },
];
