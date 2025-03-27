import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class StyleManager:
    def __init__(self):
        self.selected_style: Optional[str] = None
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        self.styles_directory = project_root / "src" / "libs" / "resume_and_cover_builder" / "resume_style"

        logging.debug(f"Project root determined as: {project_root}")
        logging.debug(f"Styles directory set to: {self.styles_directory}")

    def get_styles(self) -> Dict[str, Tuple[str, str]]:
        """
        Retrieve the available styles from the styles directory.
        Returns:
            Dict[str, Tuple[str, str]]: A dictionary mapping style names to their file names and author links.
        """
        styles_to_files = {}
        if not self.styles_directory:
            logging.warning("Styles directory is not set.")
            return styles_to_files
        logging.debug(f"Reading styles directory: {self.styles_directory}")
        try:
            files = [f for f in self.styles_directory.iterdir() if f.is_file()]
            logging.debug(f"Files found: {[f.name for f in files]}")
            for file_path in files:
                logging.debug(f"Processing file: {file_path}")
                with file_path.open("r", encoding="utf-8") as file:
                    first_line = file.readline().strip()
                    logging.debug(f"First line of file {file_path.name}: {first_line}")
                    if first_line.startswith("/*") and first_line.endswith("*/"):
                        content = first_line[2:-2].strip()
                        if "$" in content:
                            style_name, author_link = content.split("$", 1)
                            style_name = style_name.strip()
                            author_link = author_link.strip()
                            styles_to_files[style_name] = (file_path.name, author_link)
                            logging.info(f"Added style: {style_name} by {author_link}")
        except FileNotFoundError:
            logging.error(f"Directory {self.styles_directory} not found.")
        except PermissionError:
            logging.error(f"Permission denied for accessing {self.styles_directory}.")
        except Exception as e:
            logging.error(f"Unexpected error while reading styles: {e}")
        return styles_to_files

    def format_choices(self, styles_to_files: Dict[str, Tuple[str, str]]) -> List[str]:
        """
        Format the style choices for user presentation.
        Args:
            styles_to_files (Dict[str, Tuple[str, str]]): A dictionary mapping style names to their file names and author links.
        Returns:
            List[str]: A list of formatted style choices.
        """
        return [f"{style_name} (style author -> {author_link})" for style_name, (file_name, author_link) in styles_to_files.items()]

    def set_selected_style(self, selected_style: str):
        """
        Directly set the selected style.
        Args:
            selected_style (str): The name of the style to select.
        """
        self.selected_style = selected_style
        logging.info(f"Selected style set to: {self.selected_style}")

    def get_style_path(self) -> Optional[Path]:
        """
        Get the path to the selected style.
        Returns:
            Path: A Path object representing the path to the selected style file, or None if not found.
        """
        try:
            styles = self.get_styles()
            if not styles:
                logging.error("没有找到任何可用的样式文件")
                return None
                
            logging.debug(f"可用样式: {list(styles.keys())}")
            
            if not self.selected_style:
                logging.error("未选择样式")
                # 尝试使用第一个可用的样式
                if styles:
                    first_style = next(iter(styles.keys()))
                    logging.warning(f"未选择样式，使用第一个可用样式: {first_style}")
                    self.selected_style = first_style
                else:
                    return None
                    
            if self.selected_style not in styles:
                logging.error(f"选择的样式 '{self.selected_style}' 不在可用样式列表中")
                return None
                
            file_name, _ = styles[self.selected_style]
            style_path = self.styles_directory / file_name
            
            if not style_path.exists():
                logging.error(f"样式文件不存在: {style_path}")
                return None
                
            logging.info(f"样式文件路径: {style_path}")
            return style_path
        except Exception as e:
            logging.error(f"获取样式路径时出错: {str(e)}")
            return None
