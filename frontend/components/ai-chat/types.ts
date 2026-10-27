export type MessageRole = "assistant" | "user";

export type Message = {
  id: number;
  role: MessageRole;
  content: string;
  time: string;
};
