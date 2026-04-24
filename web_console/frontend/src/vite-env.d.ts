declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}

declare module '*.css' {
  const content: string;
  export default content;
}

declare module 'marked' {
  export function marked(src: string): string;
  export namespace marked {
    function parse(src: string): string;
    function setOptions(options: {
      highlight?: (code: string, lang: string) => string;
      breaks?: boolean;
      gfm?: boolean;
    }): void;
  }
}