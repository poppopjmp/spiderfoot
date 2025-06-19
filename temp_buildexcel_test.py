    def test_buildExcel(self):
        with patch('sfwebui.openpyxl.Workbook') as mock_workbook, \
             patch('sfwebui.BytesIO') as mock_bytesio:
            
            # Create mock objects
            mock_worksheet = MagicMock()
            mock_workbook.return_value.active = MagicMock()
            mock_workbook.return_value.create_sheet.return_value = mock_worksheet
            mock_workbook.return_value.__getitem__.side_effect = KeyError  # Always trigger sheet creation
            mock_workbook.return_value.save = MagicMock()
            
            # Mock BytesIO to return bytes when read()
            mock_bytesio_instance = MagicMock()
            mock_bytesio.return_value.__enter__.return_value = mock_bytesio_instance
            mock_bytesio_instance.read.return_value = b'test_excel_data'
            
            # Test with proper data structure
            result = self.webui.buildExcel([['SHEET1', 'data1', 'data2']], ['Sheet', 'Column1', 'Column2'], 0)
            self.assertIsInstance(result, bytes)
            self.assertEqual(result, b'test_excel_data')
