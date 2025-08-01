import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import numpy as np
import pandas as pd
import torch
import nibabel as nib

project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root))

from src.data.dataset import CTMetadataDataset, LabelAttacherDataset, ApplyTransforms
from src.data.utils import get_dynamic_image_path


# --- Fixtures ---

@pytest.fixture
def mock_dataframe() -> pd.DataFrame:
    """Creates a mock dataframe that matches the nested path pattern."""
    data = {
        'VolumeName': ['train_01_001.nii.gz', 'train_02_002.nii.gz'],
        'Cardiomegaly': [1, 0],
        'Atelectasis': [0, 1]
    }
    return pd.DataFrame(data)


@pytest.fixture
def pathology_columns() -> list[str]:
    """Returns a list of pathology column names."""
    return ['Cardiomegaly', 'Atelectasis']



@pytest.fixture
def temp_img_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory with a valid nested structure."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()

    # Create mock NIfTI files within the correct nested directory structure.
    # The get_dynamic_image_path function handles finding the correct file.
    # Note: For 'nested' mode, the file should NOT have the '__transformed' suffix.
    for i in range(1, 3):
        volume_name = f"train_0{i}_00{i}"
        subject_session = f"train_0{i}"
        subject_session_scan = f"train_0{i}_00{i}"

        scan_dir = img_dir / subject_session / subject_session_scan
        scan_dir.mkdir(parents=True)
        
        file_path = scan_dir / f"{volume_name}.nii.gz"
        data = np.random.rand(10, 10, 10).astype(np.float32)
        affine = np.eye(4)
        nifti_img = nib.Nifti1Image(data, affine)
        nib.save(nifti_img, file_path)
        
    return img_dir

# --- Test Classes ---

class TestCTMetadataDataset:
    """Tests for the refactored, label-agnostic CTMetadataDataset class."""

    def test_initialization(self, mock_dataframe, temp_img_dir):
        """Test basic dataset initialization without pathology columns."""
        dataset = CTMetadataDataset(
            dataframe=mock_dataframe,
            img_dir=temp_img_dir,
            path_mode="nested"
        )
        assert len(dataset.dataframe) == 2
        assert dataset.img_dir == temp_img_dir
        assert not hasattr(dataset, 'pathology_columns') # Ensure it's label-agnostic

    def test_len_method(self, mock_dataframe, temp_img_dir):
        """Test that __len__ returns the correct dataset size."""
        dataset = CTMetadataDataset(
            dataframe=mock_dataframe,
            img_dir=temp_img_dir,
            path_mode="nested"
        )
        assert len(dataset) == len(mock_dataframe)

    def test_getitem_returns_correct_path_data(self, mock_dataframe, temp_img_dir):
        """Test that __getitem__ returns a dictionary with the correct path data."""
        dataset = CTMetadataDataset(
            dataframe=mock_dataframe,
            img_dir=temp_img_dir,
            path_mode="nested"
        )
        
        # --- Test the first item ---
        volume_name = mock_dataframe.iloc[0]['VolumeName']
        item = dataset[0]
        
        # Use the actual function to generate the expected path.
        expected_path = get_dynamic_image_path(temp_img_dir, volume_name, "nested")
        
        assert isinstance(item, dict)
        assert list(item.keys()) == ["image", "volume_name"]
        
        # This assertion will now pass because both paths are generated by the same logic.
        assert item["image"] == expected_path
        assert item["volume_name"] == volume_name

class TestLabelAttacherDataset:
    """Tests for the new LabelAttacherDataset class."""

    @pytest.fixture
    def mock_image_source_dataset(self):
        """Creates a mock dataset that mimics the output of the caching pipeline."""
        class MockImageSource(torch.utils.data.Dataset):
            def __len__(self):
                return 2
            def __getitem__(self, idx):
                # This is what the dataset receives from the cache
                return {
                    "image": torch.randn(1, 10, 10, 10),
                    "image_meta_dict": {"affine": torch.eye(4)}
                }
        return MockImageSource()

    def test_getitem_merges_data_correctly(self, mock_image_source_dataset, mock_dataframe, pathology_columns):
        """Test that the dataset correctly merges cached data with labels."""
        
        # Initialize the wrapper dataset
        attacher_dataset = LabelAttacherDataset(
            image_source=mock_image_source_dataset,
            labels_df=mock_dataframe,
            pathology_columns=pathology_columns
        )

        assert len(attacher_dataset) == 2

        # Retrieve the first item
        final_item = attacher_dataset[0]

        # Define the expected output
        expected_label = torch.tensor([1, 0], dtype=torch.float32)
        
        # Assert the final dictionary is correctly formed
        assert isinstance(final_item, dict)
        assert "image" in final_item
        assert "image_meta_dict" in final_item
        assert "label" in final_item
        assert "volume_name" in final_item

        # Assert the data from both sources is present and correct
        assert isinstance(final_item["image"], torch.Tensor)
        assert torch.all(torch.eq(final_item["label"], expected_label))
        assert final_item["volume_name"] == mock_dataframe.iloc[0]['VolumeName']

class TestApplyTransforms:
    """Tests for the ApplyTransforms wrapper class (no changes needed here)."""

    def test_transform_is_applied(self):
        """Test that the transform is correctly applied to the base dataset's output."""
        mock_base_dataset = MagicMock()
        base_item = {"image": "path/to/image", "label": torch.tensor([1.0])}
        mock_base_dataset.__getitem__.return_value = base_item
        mock_base_dataset.__len__.return_value = 1

        mock_transform = MagicMock()
        transformed_item = {"image": torch.rand(1, 64, 64, 64), "label": torch.tensor([1.0])}
        mock_transform.return_value = transformed_item
        
        wrapped_dataset = ApplyTransforms(data=mock_base_dataset, transform=mock_transform)
        
        assert len(wrapped_dataset) == 1
        result = wrapped_dataset[0]

        mock_base_dataset.__getitem__.assert_called_once_with(0)
        mock_transform.assert_called_once_with(base_item)
        assert result == transformed_item