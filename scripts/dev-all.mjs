import { spawn } from "node:child_process";

const commands = [
  { name: "next", command: "npm", args: ["run", "dev"] },
  { name: "flask", command: "npm", args: ["run", "dev:flask"] }
];

const children = commands.map(({ args, command, name }) => {
  const child = spawn(command, args, {
    stdio: "inherit",
    env: process.env
  });

  child.on("exit", (code) => {
    if (code !== 0) {
      console.error(`${name} exited with code ${code}`);
    }
  });

  return child;
});

process.on("SIGINT", () => {
  for (const child of children) {
    child.kill("SIGINT");
  }
});
